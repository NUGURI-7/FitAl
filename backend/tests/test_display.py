"""展示接口:某天汇总与体重曲线,只读 new 层,零 AI 调用。"""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
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
    out = await api.day_summary(DAY, user_id=user.id)
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
    out = await api.day_summary(DAY, user_id=user.id)
    # 摄入=各顿合计之和(500+300),不是明细求和(118)——证明读的是聚合层
    assert out["intake_kcal"] == 800.0
    assert out["burn_kcal"] == 200.0
    assert [i["food_name"] for i in out["meals"][0]["items"]] == ["鸡胸脯肉"]


async def test_隔天的组不串入_归属按开始时间(db):
    user = await _user()
    await _meal(user, _utc(3, 2), 400)  # 本地 7/3 10:00
    await _meal(user, _utc(3, 17), 999)  # UTC 7/3 17:00 = 本地 7/4 01:00,属次日
    out = await api.day_summary(DAY, user_id=user.id)
    assert out["intake_kcal"] == 400.0
    assert len(out["meals"]) == 1


async def test_当天体重取最新一条_没称的日子为空(db):
    user = await _user()
    await _weight_at(user, 71.0, _utc(3, 1))  # 本地 09:00
    await _weight_at(user, 70.5, _utc(3, 8))  # 本地 16:00,更晚
    assert (await api.day_summary(DAY, user_id=user.id))["weight"] == 70.5
    assert (await api.day_summary(date(2026, 7, 4), user_id=user.id))["weight"] is None


async def test_体重曲线_只含窗口内记录_从早到晚(db):
    user = await _user()
    now = timezone.now()
    await _weight_at(user, 75.0, now - timedelta(days=40))  # 默认30天窗口外
    await _weight_at(user, 71.0, now - timedelta(days=2))
    await _weight_at(user, 72.0, now - timedelta(days=10))
    out = await api.weight_curve(user_id=user.id)
    assert [w["weight_kg"] for w in out["weights"]] == [72.0, 71.0]


async def test_用户不存在_两个接口均报404(db):
    with pytest.raises(HTTPException) as e1:
        await api.day_summary(DAY, user_id=999)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await api.weight_curve(user_id=999)
    assert e2.value.status_code == 404
