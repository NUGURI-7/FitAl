"""输入表写入链路:一句话一行、记录挂回指、失败留底、AI 轮存档。"""

import pytest

from app import api
from app.ai import parser
from app.ai.schema import ParsedFood, ParsedWeight, ParseOutput
from app.models import FoodRecord, Input, User, WeightRecord


async def _user(nick="输入测试"):
    user = await User.create(nickname=nick, height_cm=175, sex="male", birth_year=2000)
    await WeightRecord.create(user=user, weight_kg=70)
    return user


def _fake_parse(output: ParseOutput, archived: dict | None = None):
    async def fake(text, *, rounds_sink=None, **kwargs):
        if rounds_sink is not None and archived is not None:
            rounds_sink.update(archived)
        return output

    return fake


async def test_一次输入落一行且全部记录挂同一输入(db, monkeypatch):
    user = await _user()
    output = ParseOutput(
        items=[
            ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100),
            ParsedWeight(weight_kg=70.5),
        ]
    )
    monkeypatch.setattr(
        parser, "parse_text", _fake_parse(output, {"parse": {"items": 2}})
    )

    await api.chat(api.ChatIn(user_id=user.id, text="吃了根黄瓜100克,今天70.5公斤"))

    rows = await Input.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.text == "吃了根黄瓜100克,今天70.5公斤"
    assert row.status == "ok"
    assert row.ai_rounds == {"parse": {"items": 2}}  # 各轮吐出原样存档
    food = await FoodRecord.get(user=user)
    weight = await WeightRecord.filter(user=user).order_by("-id").first()
    assert food.input_id == row.id  # 一对多:多条记录指回同一行输入
    assert weight.input_id == row.id


async def test_整句失败输入留底且状态为失败(db, monkeypatch):
    user = await _user(nick="失败留底")

    async def boom(text, **kwargs):
        raise RuntimeError("重试耗尽")

    monkeypatch.setattr(parser, "parse_text", boom)

    with pytest.raises(RuntimeError):
        await api.chat(api.ChatIn(user_id=user.id, text="一句会炸的话"))

    row = await Input.get(user=user)
    assert row.text == "一句会炸的话"  # 炸了原话也留底
    assert row.status == "failed"
    assert "重试耗尽" in row.ai_rounds["error"]
    assert await FoodRecord.filter(user=user).count() == 0  # 没有半截记录


async def test_删输入行不动记录(db, monkeypatch):
    user = await _user(nick="删输入")
    output = ParseOutput(
        items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
    )
    monkeypatch.setattr(parser, "parse_text", _fake_parse(output))
    await api.chat(api.ChatIn(user_id=user.id, text="吃了根黄瓜100克"))

    await (await Input.get(user=user)).delete()

    food = await FoodRecord.get(user=user)  # raw 是唯一事实源,记录还在
    assert food.input_id is None
