import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tortoise import Tortoise, timezone
from tortoise.exceptions import IntegrityError

from app.ai import aggregate, lookup, parser
from app.ai.schema import ParsedMemory, ParsedUserFoodDef
from app.config import settings
from app.models import (
    AiMemory,
    ExerciseRecord,
    FoodRecord,
    Meal,
    Session,
    User,
    UserFood,
    WeightRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter()

SOURCE_LABEL = {
    "user_reported": "你报的",
    "user_food": "自定义",
    "food_table": "查表",
    "met_table": "查表",
    "llm_estimated": "AI估算",
}


@router.get("/health")
async def health() -> dict:
    # 校验 DB 连通,连不上直接 500
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT 1")
    return {"status": "ok"}


class ChatIn(BaseModel):
    user_id: int
    text: str = Field(min_length=1)


@router.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    """唯一对话入口(契约①)。v1 仅 intent=record:洗数据→raw→聚合→new。"""
    user = await User.get_or_none(id=body.user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    latest_weight = await WeightRecord.filter(user=user).order_by("-created_at").first()
    if latest_weight is None:
        raise HTTPException(409, "该用户还没有体重记录,无法计算消耗")

    now = timezone.now()  # aware UTC,与 auto_now_add 同一时钟,间隔计算才可靠
    profile = parser.Profile(
        weight_kg=latest_weight.weight_kg,
        height_cm=user.height_cm,
        sex=user.sex,
        birth_year=user.birth_year,
    )
    last_exercise = (
        await ExerciseRecord.filter(user=user).order_by("-created_at").first()
    )
    user_foods = {
        lookup.norm_key(uf.name): parser.UserFoodDef(
            name=uf.name,
            kcal=uf.kcal,
            protein=uf.protein,
            fat=uf.fat,
            cho=uf.cho,
            fiber=uf.fiber,
        )
        for uf in await UserFood.filter(user=user)
    }

    current_session = await aggregate.open_session(user, now)
    memory_rows = await AiMemory.filter(user=user).order_by("updated_at")

    parsed = await parser.parse_text(
        body.text,
        now=now,
        user_food_keys=frozenset(user_foods),
        open_session=await aggregate.session_summary(current_session),
        memories=";".join(r.content for r in memory_rows) or None,
    )
    resolved = parser.build_records(
        parsed,
        profile=profile,
        now=now,
        last_exercise_at=last_exercise.created_at if last_exercise else None,
        user_foods=user_foods,
    )
    cards = await persist_records(user, body.text, resolved, current_session)
    reply = compose_reply(resolved)

    async def stream():
        yield _sse("records", cards)
        yield _sse("reply", {"text": reply})
        # 回执已发完,趁连接收尾顺带做每日巩固(最佳努力,不增加用户等待)
        await maybe_consolidate_memories(user, now, memory_rows)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def maybe_consolidate_memories(user: User, now, rows: list[AiMemory]) -> None:
    """每日首次请求顺带巩固记忆:全部条目今天以前动过才触发,一天至多一次。

    最佳努力:LLM 失败静默跳过,绝不影响主链路;AI 返回空清单不执行整层替换(防误删)。
    """
    day_start = aggregate.local_day_start_utc(now)
    if len(rows) < 2 or any(r.updated_at >= day_start for r in rows):
        return
    try:
        merged = await parser.consolidate_memories([(r.kind, r.content) for r in rows])
    except Exception:
        logger.warning("记忆巩固失败,跳过", exc_info=True)
        return
    if not merged:
        return
    await AiMemory.filter(user=user).delete()
    for m in merged:
        await AiMemory.create(user=user, kind=m.kind, content=m.content)


async def persist_records(
    user: User,
    raw_text: str,
    resolved: list[parser.ResolvedRecord],
    current_session=None,
) -> list[dict]:
    """落 raw 层并逐条执行 AI 的归组判断,返回给前端的记录卡片。"""
    cards: list[dict] = []
    for r in resolved:
        if isinstance(r, parser.ResolvedWeight):
            rec = await WeightRecord.create(user=user, weight_kg=r.weight_kg)
            cards.append(
                {
                    "type": "weight",
                    "id": rec.id,
                    "weight_kg": rec.weight_kg,
                    "created_at": rec.created_at.isoformat(),
                }
            )
        elif isinstance(r, ParsedUserFoodDef):
            if r.grams is None:  # 硬校验:缺克数无法换算每100克,不入库,回执提示补
                continue
            per100 = lambda v: None if v is None else round(v / r.grams * 100, 1)  # noqa: E731
            rec, _ = await UserFood.update_or_create(  # 重复"记住"=更新定义
                user=user,
                name=r.name,
                defaults={
                    "kcal": per100(r.kcal),
                    "protein": per100(r.protein),
                    "fat": per100(r.fat),
                    "cho": per100(r.cho),
                    "fiber": per100(r.fiber),
                },
            )
            cards.append(
                {
                    "type": "user_food",
                    "id": rec.id,
                    "name": rec.name,
                    "kcal": rec.kcal,
                }
            )
        elif isinstance(r, ParsedMemory):
            rec = await AiMemory.create(user=user, kind=r.kind, content=r.content)
            cards.append(
                {
                    "type": "memory",
                    "id": rec.id,
                    "kind": rec.kind,
                    "content": rec.content,
                }
            )
        elif isinstance(r, parser.ResolvedExercise):
            rec = await ExerciseRecord.create(
                user=user,
                raw_text=raw_text,
                source=r.source,
                kcal=r.kcal,
                kcal_net=r.kcal_net,
                exercise_name=r.exercise_name,
                met=r.met,
                duration_min=r.duration_min,
                load_kg=r.load_kg,
                reps=r.reps,
            )
            current_session = await aggregate.assign_exercise(
                rec, current_session, r.starts_new_group, r.group_name
            )
            session = current_session
            cards.append(
                {
                    "type": "exercise",
                    "id": rec.id,
                    "exercise_name": rec.exercise_name,
                    "kcal": rec.kcal,
                    "kcal_net": rec.kcal_net,
                    "duration_min": rec.duration_min,
                    "load_kg": rec.load_kg,
                    "reps": rec.reps,
                    "source": rec.source,
                    "session_id": session.id,
                    "session_name": session.name,
                    "created_at": rec.created_at.isoformat(),
                }
            )
        else:
            rec = await FoodRecord.create(
                user=user,
                raw_text=raw_text,
                source=r.source,
                kcal=r.kcal,
                food_name=r.food_name,
                grams=r.grams,
                dish=r.dish,
                protein=r.protein,
                fat=r.fat,
                cho=r.cho,
                fiber=r.fiber,
            )
            meal = await aggregate.assign_food(rec, r.meal_slot)
            cards.append(
                {
                    "type": "food",
                    "id": rec.id,
                    "food_name": rec.food_name,
                    "kcal": rec.kcal,
                    "grams": rec.grams,
                    "dish": rec.dish,
                    "protein": rec.protein,
                    "fat": rec.fat,
                    "cho": rec.cho,
                    "fiber": rec.fiber,
                    "source": rec.source,
                    "meal_id": meal.id,
                    "meal_name": meal.name,
                    "created_at": rec.created_at.isoformat(),
                }
            )
    return cards


def compose_reply(resolved: list[parser.ResolvedRecord]) -> str:
    """模板拼接的一句话回执,零 LLM 成本。"已记录"只冠给真正入库的部分。"""
    if not resolved:
        return "没听出要记的内容,换个说法试试?"
    parts = []
    hints = []  # 没入库的提示(如"记住"缺克数被打回),不冠"已记录"
    for r in resolved:
        if isinstance(r, parser.ResolvedWeight):
            parts.append(f"体重 {r.weight_kg:g}kg")
        elif isinstance(r, ParsedUserFoodDef):
            if r.grams is None:
                hints.append(
                    f"{r.name} 还没记住:请补上克数(比如「{r.name}100克{r.kcal:g}千卡」)"
                )
            else:
                parts.append(
                    f"记住了 {r.name}(每100克{round(r.kcal / r.grams * 100, 1):g}千卡)"
                )
        elif isinstance(r, ParsedMemory):
            parts.append(f"记住了:{r.content}")
        elif isinstance(r, parser.ResolvedExercise):
            load = f" {r.load_kg:g}kg" if r.load_kg else ""
            reps = f"×{r.reps}" if r.reps else ""
            parts.append(
                f"{r.exercise_name}{load}{reps} ≈{r.kcal:g}千卡({SOURCE_LABEL[r.source]})"
            )
        else:
            grams = f" {r.grams:g}g" if r.grams else ""
            parts.append(
                f"{r.food_name}{grams} ≈{r.kcal:g}千卡({SOURCE_LABEL[r.source]})"
            )
    out = []
    if parts:
        out.append("已记录:" + ";".join(parts))
    if hints:
        out.append(";".join(hints))
    return ";".join(out)


# ── 修正/删除(契约②):只落 raw,触发所在聚合增量重算 ─────────────────────


class FoodPatch(BaseModel):
    grams: float | None = None
    kcal: float | None = None


class ExercisePatch(BaseModel):
    duration_min: float | None = None
    reps: int | None = None
    load_kg: float | None = None
    kcal: float | None = None


class WeightPatch(BaseModel):
    weight_kg: float


def _food_desc(rec: FoodRecord) -> str:
    grams = f"{rec.grams:g}g" if rec.grams else ""
    return f"{rec.food_name}{grams}≈{rec.kcal:g}千卡"


def _exercise_desc(rec: ExerciseRecord) -> str:
    load = f"{rec.load_kg:g}kg" if rec.load_kg else ""
    reps = f"×{rec.reps}" if rec.reps else ""
    return f"{rec.exercise_name}{load}{reps}≈{rec.kcal:g}千卡"


async def _learn_correction(user_id: int, was_estimated: bool, content: str) -> None:
    """纠正即时学:仅当被改/删的是 AI 估算记录(=用户在纠正 AI 的猜测)。"""
    if was_estimated:
        await AiMemory.create(user_id=user_id, kind="correction", content=content)


async def _bmr_per_min(user_id: int) -> float:
    """按当前档案+最新体重算每分钟基础消耗(重算运动记录用)。"""
    user = await User.get(id=user_id)
    latest = await WeightRecord.filter(user_id=user_id).order_by("-created_at").first()
    if latest is None:
        raise HTTPException(409, "该用户没有体重记录,无法重算消耗")
    bmr = lookup.bmr_kcal_per_day(
        latest.weight_kg, user.height_cm, user.sex, user.birth_year, timezone.now()
    )
    return bmr / 1440


@router.patch("/records/food/{record_id}")
async def patch_food(record_id: int, body: FoodPatch) -> dict:
    """修正饮食记录:改克数 → 重算热量营养;直接改热量 → 采用用户数。"""
    rec = await FoodRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    if body.grams is None and body.kcal is None:
        raise HTTPException(422, "至少提供 grams 或 kcal 之一")
    was_estimated = rec.source == "llm_estimated"
    old_desc = _food_desc(rec)

    if body.grams is not None:
        item = lookup.find_food(rec.food_name)
        if item:  # 表内:按新克数全套重算
            n = lookup.food_nutrition(item, body.grams)
            rec.kcal = n["kcal"]
            rec.protein, rec.fat = n["protein"], n["fat"]
            rec.cho, rec.fiber = n["cho"], n["fiber"]
        elif rec.grams:  # 表外但有旧克数:整条按比例缩放
            factor = body.grams / rec.grams
            rec.kcal = round(rec.kcal * factor, 1)
            for field in ("protein", "fat", "cho", "fiber"):
                v = getattr(rec, field)
                if v is not None:
                    setattr(rec, field, round(v * factor, 1))
        else:
            raise HTTPException(422, "该记录没有克数基准,无法按克数重算,请直接改 kcal")
        rec.grams = body.grams
    if body.kcal is not None:  # 直接改热量:采用用户数
        rec.kcal = body.kcal
        rec.source = "user_reported"
    await rec.save()

    await _learn_correction(
        rec.user_id,
        was_estimated,
        f"用户把AI估算的「{old_desc}」修正为「{_food_desc(rec)}」",
    )
    meal = await Meal.get_or_none(id=rec.meal_id) if rec.meal_id else None
    if meal:
        await aggregate.recompute_meal(meal)
    return {
        "type": "food",
        "id": rec.id,
        "food_name": rec.food_name,
        "kcal": rec.kcal,
        "grams": rec.grams,
        "protein": rec.protein,
        "fat": rec.fat,
        "cho": rec.cho,
        "fiber": rec.fiber,
        "source": rec.source,
        "meal_id": rec.meal_id,
    }


@router.patch("/records/exercise/{record_id}")
async def patch_exercise(record_id: int, body: ExercisePatch) -> dict:
    """修正运动记录:改时长 → 按 MET 重算消耗;直接改热量 → 采用用户数;
    次数/负重是训练进度描述,改动照存不影响消耗。"""
    rec = await ExerciseRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    if all(v is None for v in (body.duration_min, body.reps, body.load_kg, body.kcal)):
        raise HTTPException(422, "至少提供一个要修改的字段")
    was_estimated = rec.source == "llm_estimated"
    old_desc = _exercise_desc(rec)

    if body.reps is not None:
        rec.reps = body.reps
    if body.load_kg is not None:
        rec.load_kg = body.load_kg
    if body.duration_min is not None:
        if rec.met is None:
            raise HTTPException(422, "该记录没有 MET 值,无法按时长重算,请直接改 kcal")
        per_min = await _bmr_per_min(rec.user_id)
        rec.duration_min = body.duration_min
        rec.kcal = round(rec.met * per_min * body.duration_min, 1)
        rec.kcal_net = round((rec.met - 1) * per_min * body.duration_min, 1)
    if body.kcal is not None:  # 直接改热量:采用用户数
        rec.kcal = body.kcal
        rec.source = "user_reported"
        rec.kcal_net = (
            round(body.kcal - await _bmr_per_min(rec.user_id) * rec.duration_min, 1)
            if rec.duration_min
            else None
        )
    await rec.save()

    await _learn_correction(
        rec.user_id,
        was_estimated,
        f"用户把AI估算的「{old_desc}」修正为「{_exercise_desc(rec)}」",
    )
    session = await Session.get_or_none(id=rec.session_id) if rec.session_id else None
    if session:
        await aggregate.recompute_session(session)
    return {
        "type": "exercise",
        "id": rec.id,
        "exercise_name": rec.exercise_name,
        "kcal": rec.kcal,
        "kcal_net": rec.kcal_net,
        "duration_min": rec.duration_min,
        "load_kg": rec.load_kg,
        "reps": rec.reps,
        "source": rec.source,
        "session_id": rec.session_id,
    }


@router.delete("/records/food/{record_id}")
async def delete_food(record_id: int) -> dict:
    rec = await FoodRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    await _learn_correction(
        rec.user_id,
        rec.source == "llm_estimated",
        f"用户删除了AI估算的「{_food_desc(rec)}」(原句:{rec.raw_text})",
    )
    meal_id = rec.meal_id
    await rec.delete()
    meal = await Meal.get_or_none(id=meal_id) if meal_id else None
    if meal:
        await aggregate.recompute_meal(meal)
    return {"deleted": record_id}


@router.delete("/records/exercise/{record_id}")
async def delete_exercise(record_id: int) -> dict:
    rec = await ExerciseRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    await _learn_correction(
        rec.user_id,
        rec.source == "llm_estimated",
        f"用户删除了AI估算的「{_exercise_desc(rec)}」(原句:{rec.raw_text})",
    )
    session_id = rec.session_id
    await rec.delete()
    session = await Session.get_or_none(id=session_id) if session_id else None
    if session:
        await aggregate.recompute_session(session)
    return {"deleted": record_id}


@router.patch("/records/weight/{record_id}")
async def patch_weight(record_id: int, body: WeightPatch) -> dict:
    """修正体重记录:只改公斤数,时间戳不动;派生数字(基础代谢/曲线)读时现算,无需联动。"""
    rec = await WeightRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    rec.weight_kg = body.weight_kg
    await rec.save()
    return {"type": "weight", "id": rec.id, "weight_kg": rec.weight_kg}


@router.delete("/records/weight/{record_id}")
async def delete_weight(record_id: int) -> dict:
    rec = await WeightRecord.get_or_none(id=record_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    await rec.delete()
    return {"deleted": record_id}


# ── 展示接口(契约③④):只读 new 层,零 AI 调用 ─────────────────────────────


def _local_day_range_utc(day: date) -> tuple[datetime, datetime]:
    """本地日历日 → UTC 起止区间;顿/场归属按开始时间落在哪天算。"""
    start = datetime(
        day.year, day.month, day.day, tzinfo=ZoneInfo(settings.TIMEZONE)
    ).astimezone(UTC)
    return start, start + timedelta(days=1)


def _meal_items(records: list[FoodRecord]) -> list[dict]:
    """餐次明细分两种:带菜标签的成分归拢成"菜"(合计现算,不存表),
    无标签的平铺为单品——老数据全是单品,零迁移天然兼容。
    菜的位置=其成分首次出现的位置;同顿同名菜合并。
    """
    out: list[dict] = []
    dish_groups: dict[str, dict] = {}
    for i in records:
        entry = {
            "id": i.id,
            "food_name": i.food_name,
            "kcal": i.kcal,
            "grams": i.grams,
            "protein": i.protein,
            "fat": i.fat,
            "cho": i.cho,
            "fiber": i.fiber,
            "source": i.source,
            "created_at": i.created_at.isoformat(),
        }
        if not i.dish:
            out.append({"type": "food", **entry})
            continue
        group = dish_groups.get(i.dish)
        if group is None:
            group = {
                "type": "dish",
                "dish_name": i.dish,
                "total_grams": 0.0,
                "kcal_total": 0.0,
                "items": [],
            }
            dish_groups[i.dish] = group
            out.append(group)
        group["items"].append(entry)
        group["kcal_total"] = round(group["kcal_total"] + i.kcal, 1)
        if i.grams:
            group["total_grams"] = round(group["total_grams"] + i.grams, 1)
    return out


@router.get("/days/{day}")
async def day_summary(day: date, user_id: int) -> dict:
    """某天汇总:摄入/消耗直接读聚合层合计;当天没称重则体重为空,不沿用旧值。

    另给两个能量平衡用的数(前端算净摄入):
    - bmr_kcal:全天基础代谢,按该日结束前最近一次体重+档案算;没称过体重为空
    - burn_net_kcal:当天运动净耗合计(总耗含运动时段基础代谢,直接与全天基础代谢
      相加会重复扣,故用净耗;个别记录净耗未知时按总耗计)
    """
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    start, end = _local_day_range_utc(day)

    meals = await Meal.filter(
        user_id=user_id, start__gte=start, start__lt=end
    ).order_by("start")
    sessions = await Session.filter(
        user_id=user_id, start__gte=start, start__lt=end
    ).order_by("start")
    weight = (
        await WeightRecord.filter(
            user_id=user_id, created_at__gte=start, created_at__lt=end
        )
        .order_by("-created_at")
        .first()
    )
    latest_weight = (
        await WeightRecord.filter(user_id=user_id, created_at__lt=end)
        .order_by("-created_at")
        .first()
    )
    bmr = (
        lookup.bmr_kcal_per_day(
            latest_weight.weight_kg, user.height_cm, user.sex, user.birth_year, end
        )
        if latest_weight
        else None
    )

    meals_out = []
    for m in meals:
        items = await FoodRecord.filter(meal=m).order_by("created_at")
        meals_out.append(
            {
                "id": m.id,
                "name": m.name,
                "start": m.start.isoformat(),
                "end": m.end.isoformat(),
                "kcal_total": m.kcal_total,
                "items": _meal_items(items),
            }
        )
    sessions_out = []
    burn_net = 0.0
    for s in sessions:
        items = await ExerciseRecord.filter(session=s).order_by("created_at")
        burn_net += sum(i.kcal_net if i.kcal_net is not None else i.kcal for i in items)
        sessions_out.append(
            {
                "id": s.id,
                "name": s.name,
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "kcal_total": s.kcal_total,
                "items": [
                    {
                        "id": i.id,
                        "exercise_name": i.exercise_name,
                        "kcal": i.kcal,
                        "kcal_net": i.kcal_net,
                        "duration_min": i.duration_min,
                        "load_kg": i.load_kg,
                        "reps": i.reps,
                        "source": i.source,
                        "created_at": i.created_at.isoformat(),
                    }
                    for i in items
                ],
            }
        )
    return {
        "date": day.isoformat(),
        "intake_kcal": round(sum(m.kcal_total for m in meals), 1),
        "burn_kcal": round(sum(s.kcal_total for s in sessions), 1),
        "bmr_kcal": round(bmr, 1) if bmr is not None else None,
        "burn_net_kcal": round(burn_net, 1),
        "weight": weight.weight_kg if weight else None,
        "meals": meals_out,
        "sessions": sessions_out,
    }


@router.get("/weights")
async def weight_curve(user_id: int, days: int = 30) -> dict:
    """体重曲线:近 N 天全部记录,从早到晚。"""
    if await User.get_or_none(id=user_id) is None:
        raise HTTPException(404, "用户不存在")
    since = timezone.now() - timedelta(days=days)
    rows = await WeightRecord.filter(user_id=user_id, created_at__gte=since).order_by(
        "created_at"
    )
    return {
        "days": days,
        "weights": [
            {
                "id": r.id,
                "weight_kg": r.weight_kg,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


# ── 设置页(2026-07-09):身体档案读改 ─────────────────────────────────────


class UserPatch(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    height_cm: float | None = Field(default=None, gt=0)
    sex: Literal["male", "female"] | None = None
    birth_year: int | None = None


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "nickname": user.nickname,
        "height_cm": user.height_cm,
        "sex": user.sex,
        "birth_year": user.birth_year,
    }


@router.get("/users/{user_id}")
async def get_user(user_id: int) -> dict:
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    return _user_out(user)


@router.patch("/users/{user_id}")
async def patch_user(user_id: int, body: UserPatch) -> dict:
    """改身体档案:只发改动的字段;不回算任何已存记录,
    读时现算的数字(基础代谢/净摄入)自然采用新档案。"""
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, "至少提供一个要修改的字段")
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        await user.save()
    except IntegrityError:
        raise HTTPException(409, "昵称已被占用") from None
    return _user_out(user)


# ── 设置页(2026-07-09):自定义食物查删。改数值不设接口——
# 对话里重复"记住"即按名覆盖(user+name 唯一约束) ─────────────────────────


@router.get("/user-foods")
async def list_user_foods(user_id: int) -> dict:
    if await User.get_or_none(id=user_id) is None:
        raise HTTPException(404, "用户不存在")
    rows = await UserFood.filter(user_id=user_id).order_by("-updated_at")
    return {
        "foods": [
            {
                "id": r.id,
                "name": r.name,
                "form": r.form,
                "kcal": r.kcal,  # 每100克
                "protein": r.protein,
                "fat": r.fat,
                "cho": r.cho,
                "fiber": r.fiber,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.delete("/user-foods/{food_id}")
async def delete_user_food(food_id: int) -> dict:
    """删自定义食物:只影响以后的查表,已入库的记录数字不动。"""
    rec = await UserFood.get_or_none(id=food_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    await rec.delete()
    return {"deleted": food_id}


# ── 设置页(2026-07-09):AI 记忆查删。记忆全量注入解析 prompt,
# 错的记忆会持续误导,删除即止;纠正类由系统模板自动生成 ─────────────────────


@router.get("/memories")
async def list_memories(user_id: int) -> dict:
    if await User.get_or_none(id=user_id) is None:
        raise HTTPException(404, "用户不存在")
    rows = await AiMemory.filter(user_id=user_id).order_by("-updated_at")
    return {
        "memories": [
            {
                "id": r.id,
                "kind": r.kind,  # alias | habit | correction
                "content": r.content,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int) -> dict:
    rec = await AiMemory.get_or_none(id=memory_id)
    if rec is None:
        raise HTTPException(404, "记录不存在")
    await rec.delete()
    return {"deleted": memory_id}
