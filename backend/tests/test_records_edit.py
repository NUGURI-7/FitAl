"""修正/删除接口:重算、来源改写、聚合增量重算、纠正即时学。"""

from datetime import UTC, datetime

import pytest

from app import api
from app.ai import aggregate
from app.models import AiMemory, ExerciseRecord, FoodRecord, Meal, User, WeightRecord


def _utc(hour, minute=0) -> datetime:
    return datetime(2026, 7, 3, hour, minute, tzinfo=UTC)


async def _user(nick="修正测试"):
    user = await User.create(nickname=nick, height_cm=178, sex="male", birth_year=1997)
    await WeightRecord.create(user=user, weight_kg=70)  # BMR=1672.5
    return user


async def _food(user, name="鸡胸脯肉", grams=200.0, kcal=236.0, source="food_table"):
    rec = await FoodRecord.create(
        user=user,
        raw_text="测试",
        source=source,
        kcal=kcal,
        food_name=name,
        grams=grams,
        protein=49.2,
    )
    return await aggregate.assign_food(rec), rec


async def test_改克数_表内食物全套重算且餐次总数跟着变(db):
    user = await _user()
    meal, rec = await _food(user)  # 200g/236千卡
    card = await api.patch_food(rec.id, api.FoodPatch(grams=100), user)
    assert card["kcal"] == 118.0
    assert card["protein"] == 24.6
    assert card["source"] == "food_table"  # 改份量不改来源
    await meal.refresh_from_db()
    assert meal.kcal_total == 118.0


async def test_直接改热量_采用用户数且来源变自报(db):
    user = await _user()
    _, rec = await _food(user)
    card = await api.patch_food(rec.id, api.FoodPatch(kcal=300), user)
    assert card["kcal"] == 300
    assert card["source"] == "user_reported"


async def test_改克数_表外记录按比例缩放(db):
    user = await _user()
    _, rec = await _food(
        user, name="楼下的猪脚饭", grams=400, kcal=850, source="llm_estimated"
    )
    card = await api.patch_food(rec.id, api.FoodPatch(grams=200), user)
    assert card["kcal"] == 425.0


async def test_删除_餐次重算_删到空则整组消失(db):
    user = await _user()
    meal, rec1 = await _food(user)
    rec2 = await FoodRecord.create(
        user=user,
        raw_text="测试",
        source="food_table",
        kcal=100,
        food_name="米饭(蒸,代表值)",
        grams=100,
    )
    await aggregate.assign_food(rec2)  # 同槽自动并入同一顿

    await api.delete_food(rec2.id, user)
    await meal.refresh_from_db()
    assert meal.kcal_total == 236.0  # 只剩鸡胸肉

    await api.delete_food(rec1.id, user)
    assert await Meal.get_or_none(id=meal.id) is None  # 组空即删


async def test_删AI估算条目_产生纠正记忆(db):
    user = await _user()
    _, rec = await _food(user, name="菜籽油", grams=10, kcal=90, source="llm_estimated")
    await api.delete_food(rec.id, user)
    [memory] = await AiMemory.filter(user=user)
    assert memory.kind == "correction"
    assert "菜籽油" in memory.content


async def test_改普通记录_不产生纠正记忆(db):
    user = await _user()
    _, rec = await _food(user)  # source=food_table
    await api.patch_food(rec.id, api.FoodPatch(grams=100), user)
    assert await AiMemory.filter(user=user).count() == 0


async def test_运动改时长_按MET重算总耗净耗(db):
    user = await _user()
    rec = await ExerciseRecord.create(
        user=user,
        raw_text="测试",
        source="met_table",
        kcal=20,
        exercise_name="卧推",
        met=6.0,
        duration_min=5,
        reps=10,
    )
    session = await aggregate.assign_exercise(rec, None, False)
    card = await api.patch_exercise(rec.id, api.ExercisePatch(duration_min=10), user)
    assert card["kcal"] == pytest.approx(69.7)  # 6 × (1672.5/1440) × 10
    assert card["kcal_net"] == pytest.approx(58.1)
    await session.refresh_from_db()
    assert session.kcal_total == pytest.approx(69.7)


async def test_改体重_只改公斤数时间戳不动(db):
    user = await _user()
    rec = await WeightRecord.filter(user=user).first()  # _user 里建的 70kg
    before = rec.created_at
    card = await api.patch_weight(rec.id, api.WeightPatch(weight_kg=72.5), user)
    assert card == {"type": "weight", "id": rec.id, "weight_kg": 72.5}
    await rec.refresh_from_db()
    assert rec.weight_kg == 72.5
    assert rec.created_at == before


async def test_改体重_记录不存在报404(db):
    from fastapi import HTTPException

    user = await _user()
    with pytest.raises(HTTPException) as e:
        await api.patch_weight(99999, api.WeightPatch(weight_kg=70), user)
    assert e.value.status_code == 404


async def test_删体重_记录消失(db):
    user = await _user()
    rec = await WeightRecord.filter(user=user).first()
    res = await api.delete_weight(rec.id, user)
    assert res == {"deleted": rec.id}
    assert await WeightRecord.get_or_none(id=rec.id) is None


async def test_删体重_记录不存在报404(db):
    from fastapi import HTTPException

    user = await _user()
    with pytest.raises(HTTPException) as e:
        await api.delete_weight(99999, user)
    assert e.value.status_code == 404


async def test_运动直接改热量_净耗按时长扣基础代谢(db):
    user = await _user()
    rec = await ExerciseRecord.create(
        user=user,
        raw_text="测试",
        source="met_table",
        kcal=20,
        exercise_name="卧推",
        met=6.0,
        duration_min=5,
    )
    await aggregate.assign_exercise(rec, None, False)
    card = await api.patch_exercise(rec.id, api.ExercisePatch(kcal=100), user)
    assert card["source"] == "user_reported"
    assert card["kcal_net"] == pytest.approx(94.2)  # 100 − 5分钟基础代谢
