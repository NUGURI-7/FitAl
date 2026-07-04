from datetime import UTC, datetime

from app.ai import aggregate
from app.models import ExerciseRecord, FoodRecord, Meal, User


def _utc(month, day, hour, minute=0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


async def _user(nick="聚合测试"):
    return await User.create(nickname=nick, height_cm=178, sex="male", birth_year=1997)


async def _food(user, at: datetime, kcal=100.0):
    rec = await FoodRecord.create(
        user=user,
        raw_text="测试",
        source="food_table",
        kcal=kcal,
        food_name="米饭(蒸,代表值)",
        grams=100,
    )
    rec.created_at = at  # 测试中手工控制时间戳
    await rec.save()
    return rec


async def _exercise(user, at: datetime, kcal=20.0):
    rec = await ExerciseRecord.create(
        user=user,
        raw_text="测试",
        source="met_table",
        kcal=kcal,
        exercise_name="卧推",
        met=6.0,
        duration_min=5,
        reps=10,
    )
    rec.created_at = at
    await rec.save()
    return rec


async def test_AI判断延续_归入当前餐次并累加(db):
    user = await _user()
    m1 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 0), kcal=174), None, False
    )
    m2 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 30), kcal=236), m1, starts_new=False
    )
    assert m1.id == m2.id
    assert m2.kcal_total == 410
    assert m2.end == _utc(7, 3, 4, 30)


async def test_AI判断新开_另起一顿(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 0)), None, False)
    m2 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 5)), m1, starts_new=True
    )
    assert m1.id != m2.id


async def test_无当前组时必然新开(db):
    user = await _user()
    s1 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False
    )
    s2 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 5)), s1, False
    )
    assert s1.id == s2.id
    assert s2.kcal_total == 40


async def test_归组回写raw记录的归属外键(db):
    user = await _user()
    rec = await _food(user, _utc(7, 3, 4, 0))
    meal = await aggregate.assign_food(rec, None, False)
    await rec.refresh_from_db()
    assert rec.meal_id == meal.id


async def test_开放组只看本地时区的当天(db):
    # now = 2026-07-04 04:00 UTC = 本地(上海)12:00;本地当天从 07-03 16:00 UTC 起
    user = await _user()
    now = _utc(7, 4, 4, 0)
    await Meal.create(  # 昨天(本地 23:00)的一顿 → 不算开放
        user=user, start=_utc(7, 3, 15, 0), end=_utc(7, 3, 15, 0), kcal_total=100
    )
    assert await aggregate.open_meal(user, now) is None

    today = await Meal.create(  # 今天(本地 01:00)的一顿 → 开放
        user=user, start=_utc(7, 3, 17, 0), end=_utc(7, 3, 17, 0), kcal_total=200
    )
    found = await aggregate.open_meal(user, now)
    assert found is not None and found.id == today.id


async def test_餐次摘要含内容与热量(db):
    user = await _user()
    rec = await _food(user, _utc(7, 3, 4, 0), kcal=174)
    meal = await aggregate.assign_food(rec, None, False)
    text = await aggregate.meal_summary(meal)
    assert "米饭(蒸,代表值)" in text
    assert "174" in text


async def test_AI起名写入新开的组(db):
    user = await _user()
    meal = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 0)), None, False, name="鸡胸肉午餐"
    )
    assert meal.name == "鸡胸肉午餐"


async def test_延续组时AI新名覆盖旧名(db):
    user = await _user()
    m1 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 0)), None, False, name="午餐"
    )
    m2 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 30)), m1, False, name="鸡胸肉米饭午餐"
    )
    assert m2.id == m1.id
    assert m2.name == "鸡胸肉米饭午餐"


async def test_AI没给名_按开始时间时段兜底(db):
    # UTC 04:00 = 本地(上海)12:00 → 午餐
    user = await _user()
    meal = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 0)), None, False)
    assert meal.name == "午餐"


async def test_兜底不覆盖已有名(db):
    user = await _user()
    m1 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 0)), None, False, name="工作餐"
    )
    m2 = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 30)), m1, False)
    assert m2.name == "工作餐"


async def test_场次时段兜底(db):
    # UTC 11:00 = 本地 19:00 → 晚间训练
    user = await _user()
    session = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False
    )
    assert session.name == "晚间训练"


async def test_摘要携带组名供AI参考(db):
    user = await _user()
    meal = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 4, 0)), None, False, name="午餐"
    )
    text = await aggregate.meal_summary(meal)
    assert "「午餐」" in text
