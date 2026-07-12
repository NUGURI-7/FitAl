"""分诊管线:JSON通道微循环、体重直出、按类型并发、单科降级、餐次回填。"""

import json
from datetime import UTC, datetime

import pytest

from app.ai import pipeline
from app.ai.schema import (
    ExerciseParseOutput,
    ExerciseStrategy,
    ParsedExercise,
    ParsedFood,
    ParsedWeight,
    ParseOutput,
)

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
        return (
            ParseOutput(
                items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
            ),
            {"stub": True},
            None,
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
        return (
            ParseOutput(
                items=[ParsedFood(spoken_name="鸡蛋", name="鸡蛋(代表值)", grams=100)]
            ),
            {"stub": True},
            None,
        )

    monkeypatch.setattr(pipeline, "_extract_track", tracks)
    rounds: dict = {}
    result = await pipeline.parse_via_triage(
        "早饭吃了两个鸡蛋", now=NOW, rounds_sink=rounds
    )
    assert result.output.items[0].meal_slot == "早餐"  # 专科没填,分诊的槽回填
    assert set(rounds) == {"triage", "eat"}  # 每轮吐出都有档
    assert rounds["eat"] == {"stub": True}


async def test_管线_状态事件按阶段依次发出(monkeypatch):
    fake, _ = _fake_triage(_triage_json([{"type": "eat", "text": "吃了根黄瓜100克"}]))
    monkeypatch.setattr(pipeline, "_triage_call", fake)

    async def tracks(track, texts, **kwargs):
        return ParseOutput(items=[]), {}, None

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


def test_展开_按次数权重分摊且合计严格等于整场():
    items = [
        ParsedExercise(name="卧推", sets=5, reps=5, load_kg=40, starts_new_group=True),
        ParsedExercise(name="悬垂举腿", sets=3, reps=12),
    ]
    out = pipeline.expand_backfill(items, 90.0)
    assert len(out) == 8  # 5组+3组,每组一条
    assert all(u.sets is None for u in out)
    assert round(sum(u.duration_min for u in out), 2) == 90.0  # 合计严格=整场
    assert out[0].duration_min == round(90 * 5 / (5 * 5 + 3 * 12), 2)  # 按次数计权
    assert [u.starts_new_group for u in out] == [True] + [False] * 7  # 同一场


def test_展开_没报次数的组按已知均值计权():
    items = [
        ParsedExercise(name="卧推", sets=2),  # 没报次数
        ParsedExercise(name="悬垂举腿", sets=1, reps=10),
    ]
    out = pipeline.expand_backfill(items, 30.0)
    assert [u.duration_min for u in out] == [10.0, 10.0, 10.0]  # 均值计权=等分


def test_展开_明说时长的条目不参与分摊():
    items = [
        ParsedExercise(name="跑步", duration_min=30.0),
        ParsedExercise(name="卧推", sets=2, reps=5),
    ]
    out = pipeline.expand_backfill(items, 90.0)
    assert out[0].duration_min == 30.0  # 原样保留
    assert [u.duration_min for u in out[1:]] == [30.0, 30.0]  # 剩余60等分


def test_运动校验_策略合法性归代码():
    缺时长 = ExerciseParseOutput(
        items=[ParsedExercise(name="卧推", reps=5)],
        strategy=ExerciseStrategy(mode="backfill"),
    )
    assert any("total_duration_min" in p for p in pipeline.exercise_problems(缺时长))

    实时多组 = ExerciseParseOutput(
        items=[ParsedExercise(name="卧推", sets=5, reps=5)],
        strategy=ExerciseStrategy(mode="realtime"),
    )
    assert any("backfill" in p for p in pipeline.exercise_problems(实时多组))

    补报缺次数是合法的 = ExerciseParseOutput(
        items=[ParsedExercise(name="卧推", sets=3)],
        strategy=ExerciseStrategy(
            mode="backfill", total_duration_min=60, duration_basis="stated"
        ),
    )
    assert pipeline.exercise_problems(补报缺次数是合法的) == []


def test_展开_多组条目上的时长按整场口径清空重分摊():
    # 真机抓到:模型把"共练20分钟"填在条目时长上,原样保留会每组各占20分钟
    items = [ParsedExercise(name="卧推", sets=3, reps=8, duration_min=20.0)]
    out = pipeline.expand_backfill(items, 20.0)
    assert len(out) == 3
    assert round(sum(u.duration_min for u in out), 2) == 20.0  # 不再翻三倍


# ── 澄清表单(契约 2026-07-12):缺数的洞转澄清,答案填洞纯代码续算 ──────────


def test_澄清_补报缺整场时长出一问必答():
    out = ExerciseParseOutput(
        items=[ParsedExercise(name="卧推", sets=5, reps=5)],
        strategy=ExerciseStrategy(mode="backfill"),
    )
    clarify = pipeline.exercise_clarify(out, ["5组卧推"])
    assert clarify["text"] == "5组卧推"
    assert clarify["min_answers"] == 1
    (q,) = clarify["questions"]
    assert q["key"] == "total_duration_min" and q["required"] is True
    assert q["unit"] == "分钟"
    assert clarify["half_product"]["strategy"]["mode"] == "backfill"  # 半成品原貌随行


def test_澄清_实时条目次数时长全缺出两问至少答一():
    out = ExerciseParseOutput(
        items=[
            ParsedExercise(name="卧推", load_kg=60),  # 只报了负重,没数
            ParsedExercise(name="跑步", duration_min=30),  # 完好条目不出问题
        ],
        strategy=ExerciseStrategy(mode="realtime"),
    )
    clarify = pipeline.exercise_clarify(out, ["做了卧推", "跑了30分钟"])
    assert [q["key"] for q in clarify["questions"]] == ["reps_0", "duration_min_0"]
    assert all(not q["required"] for q in clarify["questions"])
    assert clarify["min_answers"] == 1  # 两问一组,答其一即可


def test_澄清_没有洞或只有硬伤都不转澄清():
    有数没洞 = ExerciseParseOutput(
        items=[ParsedExercise(name="卧推", reps=10)],
        strategy=ExerciseStrategy(mode="realtime"),
    )
    assert pipeline.exercise_clarify(有数没洞, ["卧推10个"]) is None

    表外无档位 = ExerciseParseOutput(
        items=[ParsedExercise(name="来历不明的动作", reps=10)],
        strategy=ExerciseStrategy(mode="realtime"),
    )
    assert pipeline.exercise_clarify(表外无档位, ["随便"]) is None  # 有数,洞不存在
    assert pipeline.exercise_blockers(表外无档位)  # 硬伤走失败路径,问用户也没用


def test_澄清_补交答案填洞且时长依据转为用户明说():
    pending = pipeline.exercise_clarify(
        ExerciseParseOutput(
            items=[ParsedExercise(name="卧推", sets=3, reps=8)],
            strategy=ExerciseStrategy(mode="backfill"),
        ),
        ["3组卧推"],
    )
    out = pipeline.resume_clarify(pending, {"total_duration_min": 30})
    assert out.strategy.total_duration_min == 30
    assert out.strategy.duration_basis == "stated"  # 补交=用户明说
    assert out.items[0].sets == 3  # 半成品其余原样保留


def test_澄清_补交乱填或没填够被打回():
    pending = pipeline.exercise_clarify(
        ExerciseParseOutput(
            items=[ParsedExercise(name="卧推")],
            strategy=ExerciseStrategy(mode="realtime"),
        ),
        ["做了卧推"],
    )
    with pytest.raises(ValueError, match="未知问题"):
        pipeline.resume_clarify(pending, {"reps_9": 10})
    with pytest.raises(ValueError, match="请填正数"):
        pipeline.resume_clarify(pending, {"reps_0": 0})
    with pytest.raises(ValueError, match="还差"):
        pipeline.resume_clarify(pending, {})  # 一个没填,洞还在
    out = pipeline.resume_clarify(pending, {"reps_0": 12})
    assert out.items[0].reps == 12
