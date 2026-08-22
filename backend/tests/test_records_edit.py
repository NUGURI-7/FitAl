"""修正/删除接口:重算、来源改写、聚合增量重算、改热量沉淀进个人食物库。"""

from datetime import UTC, datetime

import pytest

from app import api
from app.ai import aggregate
from app.models import (
    AiMemory,
    ExerciseRecord,
    FoodRecord,
    Meal,
    User,
    UserFood,
    WeightRecord,
)


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


async def test_删AI估算条目_不产生任何记忆(db):
    """删除的含义多义(记重了/没吃/确实估错),不当纠正学。"""
    user = await _user()
    _, rec = await _food(user, name="菜籽油", grams=10, kcal=90, source="llm_estimated")
    await api.delete_food(rec.id, user)
    assert await AiMemory.filter(user=user).count() == 0


async def test_改热量_按克数记录_沉淀成每100克条目(db):
    """改热量=给出了正确答案 → 进食物库,不再写中文记忆。"""
    user = await _user()
    _, rec = await _food(user, name="菜籽油", grams=10, kcal=90, source="llm_estimated")
    await api.patch_food(rec.id, api.FoodPatch(kcal=45), user)
    [uf] = await UserFood.filter(user=user)
    assert (uf.name, uf.unit) == ("菜籽油", "")
    assert uf.kcal == 450  # 10克45千卡 → 每100克450
    assert uf.kcal_per_unit is None
    assert await AiMemory.filter(user=user).count() == 0


async def test_改热量_沉淀用原话叫法而非成分表学名(db):
    """个人食物库按原话精确命中,存学名等于存了条永远查不到的。"""
    user = await _user()
    _, rec = await _food(
        user, name="米饭(代表值)", grams=600, kcal=696, source="llm_estimated"
    )
    rec.spoken_name, rec.unit, rec.unit_count = "大米饭", "碗", 3
    await rec.save()
    await api.patch_food(rec.id, api.FoodPatch(kcal=700), user)
    [uf] = await UserFood.filter(user=user)
    assert uf.name == "大米饭"  # 不是"米饭(代表值)"
    assert uf.kcal_per_unit == 233.3


async def test_改热量_没存原话叫法时退回学名(db):
    """老数据没有原话叫法列,不能因此不沉淀。"""
    user = await _user()
    _, rec = await _food(
        user, name="猪脚饭", grams=400, kcal=800, source="llm_estimated"
    )
    await api.patch_food(rec.id, api.FoodPatch(kcal=900), user)
    [uf] = await UserFood.filter(user=user)
    assert uf.name == "猪脚饭"


async def test_改热量_带量词记录_沉淀成按份条目(db):
    """整份食物按份存,克数不参与——模型倒填的克数不可信。"""
    user = await _user()
    _, rec = await _food(
        user, name="兰州拉面", grams=500, kcal=550, source="llm_estimated"
    )
    rec.unit, rec.unit_count = "碗", 1
    await rec.save()
    await api.patch_food(rec.id, api.FoodPatch(kcal=620), user)
    [uf] = await UserFood.filter(user=user)
    assert (uf.name, uf.unit) == ("兰州拉面", "碗")
    assert uf.kcal_per_unit == 620
    assert uf.kcal is None


async def test_改热量_两碗还原成一碗的热量(db):
    user = await _user()
    _, rec = await _food(
        user, name="兰州拉面", grams=1000, kcal=1100, source="llm_estimated"
    )
    rec.unit, rec.unit_count = "碗", 2
    await rec.save()
    await api.patch_food(rec.id, api.FoodPatch(kcal=1240), user)
    [uf] = await UserFood.filter(user=user)
    assert uf.kcal_per_unit == 620


async def test_改热量_重复改同一样东西_按新值覆盖不重复建条(db):
    user = await _user()
    for kcal in (620, 700):
        _, rec = await _food(
            user, name="兰州拉面", grams=500, kcal=550, source="llm_estimated"
        )
        rec.unit, rec.unit_count = "碗", 1
        await rec.save()
        await api.patch_food(rec.id, api.FoodPatch(kcal=kcal), user)
    [uf] = await UserFood.filter(user=user)
    assert uf.kcal_per_unit == 700


async def test_改热量_查表记录不沉淀(db):
    """查表命中的数是表给的,用户改它不代表表错了,不进个人库。"""
    user = await _user()
    _, rec = await _food(user)  # source=food_table
    await api.patch_food(rec.id, api.FoodPatch(kcal=999), user)
    assert await UserFood.filter(user=user).count() == 0


async def test_改克数_不沉淀(db):
    """改克数只是换算,没给出新知识。"""
    user = await _user()
    _, rec = await _food(
        user, name="兰州拉面", grams=500, kcal=550, source="llm_estimated"
    )
    await api.patch_food(rec.id, api.FoodPatch(grams=400), user)
    assert await UserFood.filter(user=user).count() == 0


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
