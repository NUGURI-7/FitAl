"""聚合 raw→new:归组判断由 AI 在解析时给出(无时间阈值常量),这里只执行。

铁律:new 层(meals/sessions)可随时从 raw 重算;AI 判断错了可改归属。
"开放组"=当天(本地时区)最近的一顿/一场,作为上下文喂给解析,也是默认归属。
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import ExerciseRecord, FoodRecord, Meal, Session, User


def local_day_start_utc(now: datetime) -> datetime:
    local = now.astimezone(ZoneInfo(settings.TIMEZONE))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def fallback_meal_name(start: datetime) -> str:
    """AI 没给名时的兜底:按开始时间(本地时区)套时段名。"""
    hour = start.astimezone(ZoneInfo(settings.TIMEZONE)).hour
    if 5 <= hour < 10:
        return "早餐"
    if 10 <= hour < 15:
        return "午餐"
    if 15 <= hour < 17:
        return "下午加餐"
    if 17 <= hour < 22:
        return "晚餐"
    return "夜宵"


def fallback_session_name(start: datetime) -> str:
    hour = start.astimezone(ZoneInfo(settings.TIMEZONE)).hour
    if 5 <= hour < 12:
        return "上午训练"
    if 12 <= hour < 18:
        return "下午训练"
    if 18 <= hour <= 23:
        return "晚间训练"
    return "凌晨训练"


async def open_meal(user: User, now: datetime) -> Meal | None:
    """当天最近一顿;跨天不延续(隔夜必然是新的一顿,无需 AI 判断)。"""
    return (
        await Meal.filter(user=user, end__gte=local_day_start_utc(now))
        .order_by("-end")
        .first()
    )


async def open_session(user: User, now: datetime) -> Session | None:
    return (
        await Session.filter(user=user, end__gte=local_day_start_utc(now))
        .order_by("-end")
        .first()
    )


async def meal_summary(meal: Meal | None) -> str | None:
    """开放餐次摘要,注入解析 prompt 供 AI 判断归组。"""
    if meal is None:
        return None
    items = await FoodRecord.filter(meal=meal).values_list("food_name", flat=True)
    tz = ZoneInfo(settings.TIMEZONE)
    label = f"「{meal.name}」" if meal.name else ""
    return (
        f"{label}{meal.start.astimezone(tz):%H:%M}-{meal.end.astimezone(tz):%H:%M} "
        f"已含 {'、'.join(items) or '空'},共{meal.kcal_total:g}千卡"
    )


async def session_summary(session: Session | None) -> str | None:
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


async def assign_food(
    record: FoodRecord, current: Meal | None, starts_new: bool, name: str = ""
) -> Meal:
    """执行 AI 的归组判断:延续 current 或新开一顿;name=AI 起的名,空则时段兜底。"""
    if current is None or starts_new:
        current = await Meal.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    if name:
        current.name = name[:64]
    elif not current.name:
        current.name = fallback_meal_name(current.start)
    current.end = max(current.end, record.created_at)
    current.kcal_total = round(current.kcal_total + record.kcal, 1)
    await current.save()
    record.meal_id = current.id
    await record.save()
    return current


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
