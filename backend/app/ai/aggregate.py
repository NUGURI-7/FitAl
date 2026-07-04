"""聚合 raw→new:写入时增量归组(纯规则);AI 起名/模糊裁决后续接入。

铁律:new 层(meals/sessions)可随时从 raw 重算;这里只做增量维护。
"""

from datetime import timedelta

from app.models import ExerciseRecord, FoodRecord, Meal, Session

MEAL_GAP_MIN = 45  # 间隔≤45分钟的饮食记录算同一顿
SESSION_GAP_MIN = 20  # 间隔≤20分钟的运动记录算同一场


async def assign_food(record: FoodRecord) -> Meal:
    """把一条饮食记录归入餐次:够近就并入最近一顿,否则开新顿。"""
    threshold = record.created_at - timedelta(minutes=MEAL_GAP_MIN)
    meal = (
        await Meal.filter(user_id=record.user_id, end__gte=threshold)
        .order_by("-end")
        .first()
    )
    if meal is None:
        meal = await Meal.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    meal.end = max(meal.end, record.created_at)
    meal.kcal_total = round(meal.kcal_total + record.kcal, 1)
    await meal.save()
    record.meal_id = meal.id
    await record.save()
    return meal


async def assign_exercise(record: ExerciseRecord) -> Session:
    """把一条运动记录归入场次,规则同餐次,间隔阈值 20 分钟。"""
    threshold = record.created_at - timedelta(minutes=SESSION_GAP_MIN)
    session = (
        await Session.filter(user_id=record.user_id, end__gte=threshold)
        .order_by("-end")
        .first()
    )
    if session is None:
        session = await Session.create(
            user_id=record.user_id,
            start=record.created_at,
            end=record.created_at,
            kcal_total=0,
        )
    session.end = max(session.end, record.created_at)
    session.kcal_total = round(session.kcal_total + record.kcal, 1)
    await session.save()
    record.session_id = session.id
    await record.save()
    return session
