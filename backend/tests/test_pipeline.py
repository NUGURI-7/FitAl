"""分诊管线:JSON通道微循环、体重直出、按类型并发、单科降级、餐次回填。"""

import json
from datetime import UTC, datetime

import pytest

from app.ai import pipeline
from app.ai.schema import ParsedFood, ParsedWeight, ParseOutput

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)


def _triage_json(segments: list[dict]) -> str:
    return json.dumps({"segments": segments}, ensure_ascii=False)


def _fake_triage(*replies: str):
    """按次序吐出预置回复的分诊替身,并记录收到的提示词。"""
    calls: list[str] = []

    async def fake(prompt: str) -> str:
        calls.append(prompt)
        return replies[min(len(calls), len(replies)) - 1]

    return fake, calls


async def test_分诊_围栏包裹的JSON也能解析(monkeypatch):
    fake, _ = _fake_triage(
        "```json\n"
        + _triage_json([{"type": "weight", "text": "今天75公斤", "weight_kg": 75}])
        + "\n```"
    )
    monkeypatch.setattr(pipeline, "_triage_call", fake)
    out = await pipeline.run_triage("今天75公斤", now=NOW, alias_memories=None)
    assert out.segments[0].weight_kg == 75


async def test_分诊_片段没照抄原文被打回后重试成功(monkeypatch):
    bad = _triage_json([{"type": "eat", "text": "吃了黄瓜一百克"}])  # 改写了原文
    good = _triage_json([{"type": "eat", "text": "吃了根黄瓜100克"}])
    fake, calls = _fake_triage(bad, good)
    monkeypatch.setattr(pipeline, "_triage_call", fake)
    out = await pipeline.run_triage("吃了根黄瓜100克", now=NOW, alias_memories=None)
    assert len(calls) == 2
    assert "不是原句子串" in calls[1]  # 带着具体错误打回
    assert out.segments[0].text == "吃了根黄瓜100克"


async def test_分诊_重试耗尽整句抛异常(monkeypatch):
    fake, calls = _fake_triage("这不是JSON")
    monkeypatch.setattr(pipeline, "_triage_call", fake)
    with pytest.raises(RuntimeError, match="分诊重试耗尽"):
        await pipeline.run_triage("随便说说", now=NOW, alias_memories=None)
    assert len(calls) == pipeline.TRIAGE_MAX_RETRIES + 1


async def test_管线_体重直出不发子任务且叫法记忆只进分诊(monkeypatch):
    fake, calls = _fake_triage(
        _triage_json([{"type": "weight", "text": "今天75公斤", "weight_kg": 75}])
    )
    monkeypatch.setattr(pipeline, "_triage_call", fake)

    async def no_track(*a, **k):
        raise AssertionError("体重不该派专科")

    monkeypatch.setattr(pipeline, "_extract_track", no_track)
    result = await pipeline.parse_via_triage(
        "今天75公斤",
        now=NOW,
        alias_memories="用户说老三样指A",
        all_memories="不该出现在分诊",
    )
    assert isinstance(result.output.items[0], ParsedWeight)
    assert result.status == "ok"
    assert "老三样" in calls[0] and "不该出现在分诊" not in calls[0]


async def test_管线_单科炸只降级该段其他照常(monkeypatch):
    fake, _ = _fake_triage(
        _triage_json(
            [
                {"type": "eat", "text": "吃了根黄瓜100克"},
                {"type": "exercise", "text": "卧推60公斤10个"},
            ]
        )
    )
    monkeypatch.setattr(pipeline, "_triage_call", fake)

    async def tracks(track, texts, **kwargs):
        if track == "exercise":
            raise RuntimeError("专科重试耗尽")
        return ParseOutput(
            items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
        )

    monkeypatch.setattr(pipeline, "_extract_track", tracks)
    result = await pipeline.parse_via_triage("吃了根黄瓜100克,卧推60公斤10个", now=NOW)
    assert result.status == "partial"
    assert "exercise" in result.failed_tracks
    assert result.failed_texts == ["卧推60公斤10个"]
    assert len(result.output.items) == 1  # 吃的照常保留


async def test_管线_餐次槽单段回填且各轮存档齐全(monkeypatch):
    fake, _ = _fake_triage(
        _triage_json([{"type": "eat", "text": "早饭吃了两个鸡蛋", "meal_slot": "早餐"}])
    )
    monkeypatch.setattr(pipeline, "_triage_call", fake)

    async def tracks(track, texts, **kwargs):
        return ParseOutput(
            items=[ParsedFood(spoken_name="鸡蛋", name="鸡蛋(代表值)", grams=100)]
        )

    monkeypatch.setattr(pipeline, "_extract_track", tracks)
    rounds: dict = {}
    result = await pipeline.parse_via_triage(
        "早饭吃了两个鸡蛋", now=NOW, rounds_sink=rounds
    )
    assert result.output.items[0].meal_slot == "早餐"  # 专科没填,分诊的槽回填
    assert set(rounds) == {"triage", "eat"}  # 每轮吐出都有档


async def test_管线_状态事件按阶段依次发出(monkeypatch):
    fake, _ = _fake_triage(_triage_json([{"type": "eat", "text": "吃了根黄瓜100克"}]))
    monkeypatch.setattr(pipeline, "_triage_call", fake)

    async def tracks(track, texts, **kwargs):
        return ParseOutput(items=[])

    monkeypatch.setattr(pipeline, "_extract_track", tracks)
    events: list[dict] = []

    async def emit(data):
        events.append(data)

    await pipeline.parse_via_triage("吃了根黄瓜100克", now=NOW, on_status=emit)
    assert events == [
        {"stage": "triage"},
        {"stage": "extract", "tracks": ["eat"]},
        {"stage": "track_done", "track": "eat"},
    ]
