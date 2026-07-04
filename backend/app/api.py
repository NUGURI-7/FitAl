import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tortoise import Tortoise, timezone

from app.ai import aggregate, parser
from app.models import ExerciseRecord, FoodRecord, User, UserFood, WeightRecord

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
        uf.name: parser.UserFoodDef(
            name=uf.name,
            unit=uf.unit,
            kcal=uf.kcal,
            protein=uf.protein,
            fat=uf.fat,
            cho=uf.cho,
            fiber=uf.fiber,
        )
        for uf in await UserFood.filter(user=user)
    }

    current_meal = await aggregate.open_meal(user, now)
    current_session = await aggregate.open_session(user, now)

    parsed = await parser.parse_text(
        body.text,
        now=now,
        user_food_names=frozenset(user_foods),
        open_meal=await aggregate.meal_summary(current_meal),
        open_session=await aggregate.session_summary(current_session),
    )
    resolved = parser.build_records(
        parsed,
        profile=profile,
        now=now,
        last_exercise_at=last_exercise.created_at if last_exercise else None,
        user_foods=user_foods,
    )
    cards = await persist_records(
        user, body.text, resolved, current_meal, current_session
    )
    reply = compose_reply(resolved)

    async def stream():
        yield _sse("records", cards)
        yield _sse("reply", {"text": reply})

    return StreamingResponse(stream(), media_type="text/event-stream")


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def persist_records(
    user: User,
    raw_text: str,
    resolved: list[parser.ResolvedRecord],
    current_meal=None,
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
                rec, current_session, r.starts_new_group
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
                protein=r.protein,
                fat=r.fat,
                cho=r.cho,
                fiber=r.fiber,
            )
            current_meal = await aggregate.assign_food(
                rec, current_meal, r.starts_new_group
            )
            meal = current_meal
            cards.append(
                {
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
                    "meal_id": meal.id,
                    "created_at": rec.created_at.isoformat(),
                }
            )
    return cards


def compose_reply(resolved: list[parser.ResolvedRecord]) -> str:
    """模板拼接的一句话回执,零 LLM 成本。"""
    if not resolved:
        return "没听出要记的内容,换个说法试试?"
    parts = []
    for r in resolved:
        if isinstance(r, parser.ResolvedWeight):
            parts.append(f"体重 {r.weight_kg:g}kg")
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
    return "已记录:" + ";".join(parts)
