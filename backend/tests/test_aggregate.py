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


# ── 餐次:时段制(2026-07-07 用户定),纯代码零 AI ──────────────────────────


async def test_时钟落槽_本地各时段对应正确(db):
    # UTC+8:本地 8:00 早餐 / 12:00 午餐 / 16:00 下午茶 / 21:00 晚餐 / 23:00 其余
    assert aggregate.meal_slot_for(_utc(7, 3, 0, 0)) == "早餐"
    assert aggregate.meal_slot_for(_utc(7, 3, 4, 0)) == "午餐"
    assert aggregate.meal_slot_for(_utc(7, 3, 8, 0)) == "下午茶"
    assert aggregate.meal_slot_for(_utc(7, 3, 13, 0)) == "晚餐"
    assert aggregate.meal_slot_for(_utc(7, 3, 15, 0)) == "其余"


async def test_同时段自动合并并累加(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 0), kcal=174))
    m2 = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 30), kcal=236))
    assert m1.id == m2.id
    assert m2.name == "午餐"
    assert m2.kcal_total == 410
    assert m2.end == _utc(7, 3, 4, 30)


async def test_不同时段各自成组(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _utc(7, 3, 4, 0)))  # 午餐
    m2 = await aggregate.assign_food(await _food(user, _utc(7, 3, 8, 0)))  # 下午茶
    assert m1.id != m2.id
    assert (m1.name, m2.name) == ("午餐", "下午茶")


async def test_明说的餐次优先于时钟(db):
    # 本地 22:30(其余时段)明说"早餐" → 归入早餐槽
    user = await _user()
    meal = await aggregate.assign_food(await _food(user, _utc(7, 3, 14, 30)), "早餐")
    assert meal.name == "早餐"


async def test_明说与时钟归入同一天同一槽则合并(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _utc(7, 3, 0, 0)))  # 8:00 早餐
    m2 = await aggregate.assign_food(
        await _food(user, _utc(7, 3, 14, 30)), "早餐"
    )  # 22:30 明说早餐
    assert m1.id == m2.id


async def test_同名时段跨天不合并(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _utc(7, 2, 13, 0)))  # 7/2 晚餐
    m2 = await aggregate.assign_food(await _food(user, _utc(7, 3, 13, 0)))  # 7/3 晚餐
    assert m1.id != m2.id
    assert m1.name == m2.name == "晚餐"


async def test_归组回写raw记录的归属外键(db):
    user = await _user()
    rec = await _food(user, _utc(7, 3, 4, 0))
    meal = await aggregate.assign_food(rec)
    await rec.refresh_from_db()
    assert rec.meal_id == meal.id


# ── 场次:仍由 AI 判断归组,代码执行(不变) ───────────────────────────────


async def test_场次_AI判断延续则累加(db):
    user = await _user()
    s1 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False
    )
    s2 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 5)), s1, False
    )
    assert s1.id == s2.id
    assert s2.kcal_total == 40


async def test_场次_AI判断新开则另起(db):
    user = await _user()
    s1 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False
    )
    s2 = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 5)), s1, True
    )
    assert s1.id != s2.id


async def test_场次_开放场次只看本地时区的当天(db):
    # now = 2026-07-04 04:00 UTC = 本地(上海)12:00;本地当天从 07-03 16:00 UTC 起
    user = await _user()
    now = _utc(7, 4, 4, 0)
    from app.models import Session

    await Session.create(  # 昨天(本地 23:00)的一场 → 不算开放
        user=user, start=_utc(7, 3, 15, 0), end=_utc(7, 3, 15, 0), kcal_total=100
    )
    assert await aggregate.open_session(user, now) is None

    today = await Session.create(  # 今天(本地 01:00)的一场 → 开放
        user=user, start=_utc(7, 3, 17, 0), end=_utc(7, 3, 17, 0), kcal_total=200
    )
    found = await aggregate.open_session(user, now)
    assert found is not None and found.id == today.id


async def test_场次_AI起名写入(db):
    user = await _user()
    session = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False, "晚间胸部训练"
    )
    assert session.name == "晚间胸部训练"


async def test_场次_AI没给名按时段兜底(db):
    # UTC 11:00 = 本地 19:00 → 晚间训练
    user = await _user()
    session = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False
    )
    assert session.name == "晚间训练"


async def test_场次_摘要含内容与组名(db):
    user = await _user()
    session = await aggregate.assign_exercise(
        await _exercise(user, _utc(7, 3, 11, 0)), None, False, "晚间训练"
    )
    text = await aggregate.session_summary(session)
    assert "卧推" in text
    assert "「晚间训练」" in text


async def test_删除餐次成员_重算与组空即删(db):
    user = await _user()
    rec1 = await _food(user, _utc(7, 3, 4, 0), kcal=174)
    rec2 = await _food(user, _utc(7, 3, 4, 30), kcal=236)
    meal = await aggregate.assign_food(rec1)
    await aggregate.assign_food(rec2)

    await rec2.delete()
    await meal.refresh_from_db()
    await aggregate.recompute_meal(meal)
    assert meal.kcal_total == 174

    await rec1.delete()
    await aggregate.recompute_meal(meal)
    assert await Meal.get_or_none(id=meal.id) is None
