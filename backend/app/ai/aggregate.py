"""聚合 raw→new。

餐次(2026-07-07 用户定,时段制):明说哪顿归哪顿,否则按本地时钟落固定时段;
组名=时段名,一天每时段至多一组,纯代码零 AI。
场次:归组判断仍由 AI 在解析时给出(无时间阈值常量),这里只执行。
铁律:new 层(meals/sessions)可随时从 raw 重算;判断错了可改归属。
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import ExerciseRecord, FoodRecord, Meal, Session, User


def local_day_start_utc(now: datetime) -> datetime:
    local = now.astimezone(ZoneInfo(settings.TIMEZONE))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def meal_slot_for(at: datetime) -> str:
    """没明说哪顿时,按本地时钟落固定时段(边界:5/10/15/17/22)。"""
    hour = at.astimezone(ZoneInfo(settings.TIMEZONE)).hour
    if 5 <= hour < 10:
        return "早餐"
    if 10 <= hour < 15:
        return "午餐"
    if 15 <= hour < 17:
        return "下午茶"
    if 17 <= hour < 22:
        return "晚餐"
    return "其余"


def fallback_session_name(start: datetime) -> str:
    hour = start.astimezone(ZoneInfo(settings.TIMEZONE)).hour
    if 5 <= hour < 12:
        return "上午训练"
    if 12 <= hour < 18:
        return "下午训练"
    if 18 <= hour <= 23:
        return "晚间训练"
    return "凌晨训练"


async def open_session(user: User, now: datetime) -> Session | None:
    """当天最近一场训练;跨天不延续(隔夜必然是新一场,无需 AI 判断)。"""
    return (
        await Session.filter(user=user, end__gte=local_day_start_utc(now))
        .order_by("-end")
        .first()
    )


async def session_summary(session: Session | None) -> str | None:
    """开放场次摘要,注入解析 prompt 供 AI 判断场次归组。"""
    if session is None:
        return None
    items = await ExerciseRecord.filter(session=session).values_list(
        "exercise_name", flat=True
    )
    tz = ZoneInfo(settings.TIMEZONE)
    label = f"「{session.name}」" if session.name else ""
    return (
        f"{label}{session.start.astimezone(tz):%H:%M}-{session.end.astimezone(tz):%H:%M} "
        f"已含 {'、'.join(items) or '空'},共{session.kcal_total:g}千卡"
    )


async def recompute_meal(meal: Meal) -> None:
    """修正/删除后的增量重算:总热量/起止时间从剩余成员重推;无成员则删组。"""
    items = await FoodRecord.filter(meal=meal)
    if not items:
        await meal.delete()
        return
    meal.start = min(i.created_at for i in items)
    meal.end = max(i.created_at for i in items)
    meal.kcal_total = round(sum(i.kcal for i in items), 1)
    await meal.save()


async def recompute_session(session: Session) -> None:
    items = await ExerciseRecord.filter(session=session)
    if not items:
        await session.delete()
        return
    session.start = min(i.created_at for i in items)
    session.end = max(i.created_at for i in items)
    session.kcal_total = round(sum(i.kcal for i in items), 1)
    await session.save()


async def assign_food(record: FoodRecord, explicit_slot: str | None = None) -> Meal:
    """时段制归组:明说的餐次优先,否则按时钟落槽;一天每槽至多一组,同槽合并。"""
    slot = explicit_slot or meal_slot_for(record.created_at)
    day_start = local_day_start_utc(record.created_at)
    day_end = day_start + timedelta(days=1)
    meal = await Meal.filter(
        user_id=record.user_id, name=slot, start__gte=day_start, start__lt=day_end
    ).first()
    if meal is None:
        meal = await Meal.create(
            user_id=record.user_id,
            name=slot,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    meal.start = min(meal.start, record.created_at)
    meal.end = max(meal.end, record.created_at)
    meal.kcal_total = round(meal.kcal_total + record.kcal, 1)
    await meal.save()
    record.meal_id = meal.id
    await record.save()
    return meal


async def assign_exercise(
    record: ExerciseRecord, current: Session | None, starts_new: bool, name: str = ""
) -> Session:
    if current is None or starts_new:
        current = await Session.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    if name:
        current.name = name[:64]
    elif not current.name:
        current.name = fallback_session_name(current.start)
    current.end = max(current.end, record.created_at)
    current.kcal_total = round(current.kcal_total + record.kcal, 1)
    await current.save()
    record.session_id = current.id
    await record.save()
    return current
