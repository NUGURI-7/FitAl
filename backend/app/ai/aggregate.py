"""聚合 raw→new:归组判断由 AI 在解析时给出(无时间阈值常量),这里只执行。

铁律:new 层(meals/sessions)可随时从 raw 重算;AI 判断错了可改归属。
"开放组"=当天(本地时区)最近的一顿/一场,作为上下文喂给解析,也是默认归属。
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import ExerciseRecord, FoodRecord, Meal, Session, User


def _local_day_start_utc(now: datetime) -> datetime:
    local = now.astimezone(ZoneInfo(settings.TIMEZONE))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def open_meal(user: User, now: datetime) -> Meal | None:
    """当天最近一顿;跨天不延续(隔夜必然是新的一顿,无需 AI 判断)。"""
    return (
        await Meal.filter(user=user, end__gte=_local_day_start_utc(now))
        .order_by("-end")
        .first()
    )


async def open_session(user: User, now: datetime) -> Session | None:
    return (
        await Session.filter(user=user, end__gte=_local_day_start_utc(now))
        .order_by("-end")
        .first()
    )


async def meal_summary(meal: Meal | None) -> str | None:
    """开放餐次摘要,注入解析 prompt 供 AI 判断归组。"""
    if meal is None:
        return None
    items = await FoodRecord.filter(meal=meal).values_list("food_name", flat=True)
    tz = ZoneInfo(settings.TIMEZONE)
    return (
        f"{meal.start.astimezone(tz):%H:%M}-{meal.end.astimezone(tz):%H:%M} "
        f"已含 {'、'.join(items) or '空'},共{meal.kcal_total:g}千卡"
    )


async def session_summary(session: Session | None) -> str | None:
    if session is None:
        return None
    items = await ExerciseRecord.filter(session=session).values_list(
        "exercise_name", flat=True
    )
    tz = ZoneInfo(settings.TIMEZONE)
    return (
        f"{session.start.astimezone(tz):%H:%M}-{session.end.astimezone(tz):%H:%M} "
        f"已含 {'、'.join(items) or '空'},共{session.kcal_total:g}千卡"
    )


async def assign_food(
    record: FoodRecord, current: Meal | None, starts_new: bool
) -> Meal:
    """执行 AI 的归组判断:延续 current 或新开一顿。"""
    if current is None or starts_new:
        current = await Meal.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    current.end = max(current.end, record.created_at)
    current.kcal_total = round(current.kcal_total + record.kcal, 1)
    await current.save()
    record.meal_id = current.id
    await record.save()
    return current


async def assign_exercise(
    record: ExerciseRecord, current: Session | None, starts_new: bool
) -> Session:
    if current is None or starts_new:
        current = await Session.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    current.end = max(current.end, record.created_at)
    current.kcal_total = round(current.kcal_total + record.kcal, 1)
    await current.save()
    record.session_id = current.id
    await record.save()
    return current
