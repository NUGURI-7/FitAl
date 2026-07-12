"""展示接口:某天汇总与体重曲线,只读 new 层,零 AI 调用。"""

from datetime import UTC, date, datetime, timedelta

import pytest
from tortoise import timezone

from app import api
from app.models import FoodRecord, Meal, Session, User, WeightRecord


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=UTC)


DAY = date(2026, 7, 3)  # 本地(Asia/Shanghai)7月3日 = UTC 7/2 16:00 ~ 7/3 16:00


async def _user(nick="展示测试"):
    return await User.create(nickname=nick, height_cm=178, sex="male", birth_year=1997)


async def _meal(user, start, kcal_total, name="测试餐"):
    return await Meal.create(
        user=user, name=name, start=start, end=start, kcal_total=kcal_total
    )


async def _session(user, start, kcal_total, name="测试训练"):
    return await Session.create(
        user=user, name=name, start=start, end=start, kcal_total=kcal_total
    )


async def _weight_at(user, weight_kg, created_at):
    # created_at 是 auto_now_add,建完用 queryset 改到目标时刻
    rec = await WeightRecord.create(user=user, weight_kg=weight_kg)
    await WeightRecord.filter(id=rec.id).update(created_at=created_at)
    return rec


async def test_空的一天_摄入消耗为零_体重为空_列表为空(db):
    user = await _user()
    out = await api.day_summary(DAY, user=user)
    assert out["intake_kcal"] == 0
    assert out["burn_kcal"] == 0
    assert out["weight"] is None
    assert out["meals"] == [] and out["sessions"] == []


async def test_日汇总_摄入消耗读聚合层合计_并挂明细(db):
    user = await _user()
    meal1 = await _meal(user, _utc(3, 0), 500)  # 本地 08:00
    await _meal(user, _utc(3, 4), 300)  # 本地 12:00
    await _session(user, _utc(3, 10), 200)  # 本地 18:00
    await FoodRecord.create(
        user=user,
        raw_text="测试",
        source="food_table",
        kcal=118,
        food_name="鸡胸脯肉",
        grams=100,
        meal=meal1,
    )
    out = await api.day_summary(DAY, user=user)
    # 摄入=各顿合计之和(500+300),不是明细求和(118)——证明读的是聚合层
    assert out["intake_kcal"] == 800.0
    assert out["burn_kcal"] == 200.0
    assert [i["food_name"] for i in out["meals"][0]["items"]] == ["鸡胸脯肉"]


async def test_隔天的组不串入_归属按开始时间(db):
    user = await _user()
    await _meal(user, _utc(3, 2), 400)  # 本地 7/3 10:00
    await _meal(user, _utc(3, 17), 999)  # UTC 7/3 17:00 = 本地 7/4 01:00,属次日
    out = await api.day_summary(DAY, user=user)
    assert out["intake_kcal"] == 400.0
    assert len(out["meals"]) == 1


async def test_当天体重取最新一条_没称的日子为空(db):
    user = await _user()
    await _weight_at(user, 71.0, _utc(3, 1))  # 本地 09:00
    await _weight_at(user, 70.5, _utc(3, 8))  # 本地 16:00,更晚
    assert (await api.day_summary(DAY, user=user))["weight"] == 70.5
    assert (await api.day_summary(date(2026, 7, 4), user=user))["weight"] is None


async def test_体重曲线_只含窗口内记录_从早到晚(db):
    user = await _user()
    now = timezone.now()
    await _weight_at(user, 75.0, now - timedelta(days=40))  # 默认30天窗口外
    await _weight_at(user, 71.0, now - timedelta(days=2))
    await _weight_at(user, 72.0, now - timedelta(days=10))
    out = await api.weight_curve(user=user)
    assert [w["weight_kg"] for w in out["weights"]] == [72.0, 71.0]


async def test_日汇总_返回全天基础代谢与运动净耗合计(db):
    user = await _user()
    await _weight_at(user, 70.0, _utc(2, 1))  # 该日之前已称过体重
    session = await _session(user, _utc(3, 10), 150)
    from app.models import ExerciseRecord

    e1 = await ExerciseRecord.create(
        user=user,
        raw_text="测试",
        source="met_table",
        kcal=100,
        kcal_net=80,
        exercise_name="卧推",
    )
    e2 = await ExerciseRecord.create(
        user=user,
        raw_text="测试",
        source="user_reported",
        kcal=50,
        kcal_net=None,  # 自报热量,净耗未知
        exercise_name="跑步",
    )
    e1.session = session
    e2.session = session
    await e1.save()
    await e2.save()

    out = await api.day_summary(DAY, user=user)
    # 70kg/178cm/男/1997 → Mifflin-St Jeor 全天 1672.5
    assert out["bmr_kcal"] == pytest.approx(1672.5, abs=0.1)
    assert out["burn_net_kcal"] == 130.0  # 80 + 50(净耗未知按总耗计)


async def test_从未称重_基础代谢为空(db):
    user = await _user()
    out = await api.day_summary(DAY, user=user)
    assert out["bmr_kcal"] is None
    assert out["burn_net_kcal"] == 0


async def test_日汇总_只看自己的_不串别人数据(db):
    user = await _user()
    other = await _user(nick="别人")
    await _meal(other, _utc(3, 0), 700)
    out = await api.day_summary(DAY, user=user)
    assert out["meals"] == [] and out["intake_kcal"] == 0


async def test_日汇总_带菜标签的成分归拢成菜且合计现算(db):
    user = await _user()
    meal = await _meal(user, _utc(3, 0), 700)
    for name, kcal, grams, dish in [
        ("鸡胸脯肉", 118, 100, None),  # 单品
        ("面包", 315, 90, "毛毛虫面包"),
        ("奶油", 263.7, 30, "毛毛虫面包"),
    ]:
        await FoodRecord.create(
            user=user,
            raw_text="测试",
            source="food_table",
            kcal=kcal,
            food_name=name,
            grams=grams,
            dish=dish,
            meal=meal,
        )
    out = await api.day_summary(DAY, user=user)
    [plain, dish] = out["meals"][0]["items"]
    assert plain["type"] == "food" and plain["food_name"] == "鸡胸脯肉"
    assert dish["type"] == "dish" and dish["dish_name"] == "毛毛虫面包"
    assert dish["total_grams"] == 120.0  # 90+30,现算
    assert dish["kcal_total"] == 578.7  # 315+263.7,现算
    assert [i["food_name"] for i in dish["items"]] == ["面包", "奶油"]


async def test_日汇总_老数据无菜标签全部平铺为单品(db):
    user = await _user()
    meal = await _meal(user, _utc(3, 0), 350)
    for name in ("米饭(蒸，代表值)", "鸡蛋(代表值)"):
        await FoodRecord.create(
            user=user,
            raw_text="测试",
            source="food_table",
            kcal=100,
            food_name=name,
            grams=100,
            meal=meal,
        )
    out = await api.day_summary(DAY, user=user)
    assert [i["type"] for i in out["meals"][0]["items"]] == ["food", "food"]
