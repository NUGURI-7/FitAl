"""澄清补交接口:填洞入库零AI、归属校验、防重复、没填够打回(契约 2026-07-12)。"""

import pytest
from fastapi import HTTPException

from app import api
from app.models import ExerciseRecord, Input, User, WeightRecord


async def _user(nick="澄清测试"):
    user = await User.create(nickname=nick, height_cm=175, sex="male", birth_year=2000)
    await WeightRecord.create(user=user, weight_kg=70)
    return user


def _pending_realtime() -> dict:
    """实时单组缺次数与时长的半成品(重试尽只剩缺数的洞)。"""
    return {
        "text": "做了卧推",
        "questions": [
            {
                "key": "reps_0",
                "prompt": "卧推:做了几个?",
                "unit": "个",
                "required": False,
            },
            {
                "key": "duration_min_0",
                "prompt": "卧推:练了多久?",
                "unit": "分钟",
                "required": False,
            },
        ],
        "min_answers": 1,
        "half_product": {
            "items": [
                {
                    "name": "卧推",
                    "load_kg": 60,
                    "starts_new_group": True,
                    "group_name": "晚间胸部训练",
                }
            ],
            "strategy": {"mode": "realtime"},
        },
        "status_after": "ok",
    }


async def _pending_row(user, pending: dict | None = None) -> Input:
    return await Input.create(
        user=user,
        text="做了卧推",
        status="need_clarify",
        pending_clarify=pending or _pending_realtime(),
    )


async def test_补交时长后查表算数入库并清待补(db):
    user = await _user()
    row = await _pending_row(user)

    resp = await api.clarify_input(
        row.id, api.ClarifyIn(answers={"duration_min_0": 20}), user
    )

    (card,) = resp["records"]
    assert card["type"] == "exercise" and card["exercise_name"] == "卧推"
    assert card["duration_min"] == 20
    assert card["kcal"] > 0 and card["source"] == "met_table"  # 查表算数归代码
    assert card["session_id"] and card["session_name"] == "晚间胸部训练"  # 照常归组
    assert "已记录" in resp["reply"]
    await row.refresh_from_db()
    assert row.status == "ok"  # 待补态收场
    assert row.pending_clarify is None
    rec = await ExerciseRecord.get(user=user)
    assert rec.input_id == row.id  # 记录挂回同一输入行


async def test_补交整场时长展开每组一条合计等于整场(db):
    user = await _user(nick="补报澄清")
    pending = {
        "text": "3组卧推每组8个",
        "questions": [
            {
                "key": "total_duration_min",
                "prompt": "这场一共练了多久?",
                "unit": "分钟",
                "required": True,
            }
        ],
        "min_answers": 1,
        "half_product": {
            "items": [{"name": "卧推", "sets": 3, "reps": 8}],
            "strategy": {"mode": "backfill"},
        },
        "status_after": "ok",
    }
    row = await _pending_row(user, pending)

    resp = await api.clarify_input(
        row.id, api.ClarifyIn(answers={"total_duration_min": 30}), user
    )

    assert len(resp["records"]) == 3  # 每组一条
    assert round(sum(c["duration_min"] for c in resp["records"]), 2) == 30.0
    assert len({c["session_id"] for c in resp["records"]}) == 1  # 同一场


async def test_别人的输入行如同不存在404(db):
    owner = await _user(nick="行主人")
    outsider = await _user(nick="外人")
    row = await _pending_row(owner)
    with pytest.raises(HTTPException) as e:
        await api.clarify_input(row.id, api.ClarifyIn(answers={"reps_0": 10}), outsider)
    assert e.value.status_code == 404


async def test_已补过再交409防重复入库(db):
    user = await _user(nick="防重复")
    row = await _pending_row(user)
    await api.clarify_input(row.id, api.ClarifyIn(answers={"reps_0": 10}), user)
    with pytest.raises(HTTPException) as e:
        await api.clarify_input(row.id, api.ClarifyIn(answers={"reps_0": 10}), user)
    assert e.value.status_code == 409
    assert await ExerciseRecord.filter(user=user).count() == 1  # 没记两遍


async def test_没填够或乱填400带缺啥(db):
    user = await _user(nick="没填够")
    row = await _pending_row(user)
    with pytest.raises(HTTPException) as e:
        await api.clarify_input(row.id, api.ClarifyIn(answers={}), user)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        await api.clarify_input(row.id, api.ClarifyIn(answers={"reps_9": 10}), user)
    assert e.value.status_code == 400 and "未知问题" in e.value.detail
    await row.refresh_from_db()
    assert row.status == "need_clarify"  # 打回不消耗待补态,可以再交
    assert await ExerciseRecord.filter(user=user).count() == 0
