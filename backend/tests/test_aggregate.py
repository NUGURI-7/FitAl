from datetime import UTC, datetime

from app.ai import aggregate
from app.models import ExerciseRecord, FoodRecord, User


def _at(hour: int, minute: int) -> datetime:
    # 生产配置 use_tz=True,时间戳一律 aware UTC
    return datetime(2026, 7, 3, hour, minute, tzinfo=UTC)


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
    rec.created_at = at  # 测试中手工控制时间戳以模拟间隔
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


async def test_间隔45分钟内的饮食归同一餐_热量累加(db):
    user = await _user()
    r1 = await _food(user, _at(12, 0), kcal=174)
    r2 = await _food(user, _at(12, 30), kcal=236)
    m1 = await aggregate.assign_food(r1)
    m2 = await aggregate.assign_food(r2)
    assert m1.id == m2.id
    assert m2.kcal_total == 410
    assert m2.start == _at(12, 0)
    assert m2.end == _at(12, 30)


async def test_间隔超45分钟的饮食分成两餐(db):
    user = await _user()
    m1 = await aggregate.assign_food(await _food(user, _at(12, 0)))
    m2 = await aggregate.assign_food(await _food(user, _at(13, 0)))
    assert m1.id != m2.id


async def test_运动间隔20分钟内同场_超时开新场(db):
    user = await _user()
    s1 = await aggregate.assign_exercise(await _exercise(user, _at(19, 0)))
    s2 = await aggregate.assign_exercise(await _exercise(user, _at(19, 15)))
    s3 = await aggregate.assign_exercise(await _exercise(user, _at(19, 40)))
    assert s1.id == s2.id
    assert s3.id != s2.id
    assert s2.kcal_total == 40


async def test_归组回写raw记录的归属外键(db):
    user = await _user()
    rec = await _food(user, _at(12, 0))
    meal = await aggregate.assign_food(rec)
    await rec.refresh_from_db()
    assert rec.meal_id == meal.id


async def test_不同用户的记录不会归入同一组(db):
    u1 = await _user("甲")
    u2 = await _user("乙")
    m1 = await aggregate.assign_food(await _food(u1, _at(12, 0)))
    m2 = await aggregate.assign_food(await _food(u2, _at(12, 5)))
    assert m1.id != m2.id
