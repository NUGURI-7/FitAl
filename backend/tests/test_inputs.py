"""输入表写入链路(新管线接入后):落底、挂标、失败回人话、部分降级状态。"""

from app import api
from app.ai import pipeline
from app.ai.schema import ParsedFood, ParsedWeight, ParseOutput
from app.models import FoodRecord, Input, User, WeightRecord


async def _user(nick="输入测试"):
    user = await User.create(nickname=nick, height_cm=175, sex="male", birth_year=2000)
    await WeightRecord.create(user=user, weight_kg=70)
    return user


def _fake_pipeline(result: pipeline.PipelineResult, archived: dict | None = None):
    async def fake(text, *, rounds_sink=None, on_status=None, **kwargs):
        if rounds_sink is not None and archived is not None:
            rounds_sink.update(archived)
        return result

    return fake


async def _drain(resp) -> str:
    """消费 SSE 流(解析与入库在流内发生),返回全文供断言。"""
    return "".join([chunk async for chunk in resp.body_iterator])


async def test_一次输入落一行且全部记录挂同一输入(db, monkeypatch):
    user = await _user()
    result = pipeline.PipelineResult(
        output=ParseOutput(
            items=[
                ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100),
                ParsedWeight(weight_kg=70.5),
            ]
        )
    )
    monkeypatch.setattr(
        pipeline, "parse_via_triage", _fake_pipeline(result, {"triage": {"seg": 2}})
    )

    resp = await api.chat(api.ChatIn(text="吃了根黄瓜100克,今天70.5公斤"), user)
    body = await _drain(resp)

    rows = await Input.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.text == "吃了根黄瓜100克,今天70.5公斤"
    assert row.status == "ok"
    assert row.ai_rounds == {"triage": {"seg": 2}}  # 各轮吐出原样存档
    food = await FoodRecord.get(user=user)
    weight = await WeightRecord.filter(user=user).order_by("-id").first()
    assert food.input_id == row.id  # 一对多:多条记录指回同一行输入
    assert weight.input_id == row.id
    # 事件顺序:算数入库状态 → 记录卡片 → 回执
    assert body.index("saving") < body.index("records") < body.index("reply")


async def test_整句失败回人话且留底不炸500(db, monkeypatch):
    user = await _user(nick="失败留底")

    async def boom(text, **kwargs):
        raise RuntimeError("分诊重试耗尽")

    monkeypatch.setattr(pipeline, "parse_via_triage", boom)

    resp = await api.chat(api.ChatIn(text="一句会炸的话"), user)
    body = await _drain(resp)  # 不抛异常:错例④,回人话

    assert "没解析出来" in body
    row = await Input.get(user=user)
    assert row.text == "一句会炸的话"  # 炸了原话也留底
    assert row.status == "failed"
    assert "分诊重试耗尽" in row.ai_rounds["error"]
    assert await FoodRecord.filter(user=user).count() == 0  # 没有半截记录


async def test_部分降级状态partial且回执明说没听懂(db, monkeypatch):
    user = await _user(nick="部分降级")
    result = pipeline.PipelineResult(
        output=ParseOutput(
            items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
        ),
        failed_tracks={"exercise": "重试耗尽"},
        failed_texts=["卧推60公斤10个"],
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))

    resp = await api.chat(api.ChatIn(text="吃了根黄瓜100克,卧推60公斤10个"), user)
    body = await _drain(resp)

    assert "已记录" in body and "没听懂" in body and "卧推60公斤10个" in body
    row = await Input.get(user=user)
    assert row.status == "partial"  # 半句留底,半句照常入库
    assert await FoodRecord.filter(user=user).count() == 1


async def test_澄清段挂起待补且流里推澄清事件(db, monkeypatch):
    user = await _user(nick="澄清挂起")
    clarify = {
        "text": "做了卧推",
        "questions": [
            {
                "key": "reps_0",
                "prompt": "卧推:做了几个?",
                "unit": "个",
                "required": False,
            }
        ],
        "min_answers": 1,
        "half_product": {"items": [{"name": "卧推"}], "strategy": {"mode": "realtime"}},
    }
    result = pipeline.PipelineResult(
        output=ParseOutput(
            items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
        ),
        clarify=clarify,
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))

    resp = await api.chat(api.ChatIn(text="吃了根黄瓜100克,做了卧推"), user)
    body = await _drain(resp)

    # 事件顺序:记录卡片 → 澄清事件 → 回执;回执明说差个数
    assert body.index("records") < body.index("clarify") < body.index("reply")
    assert "做了几个" in body and "还差个数" in body
    row = await Input.get(user=user)
    assert row.status == "need_clarify"
    assert row.pending_clarify["status_after"] == "ok"  # 补交成功后该回的状态
    assert row.pending_clarify["min_answers"] == 1
    assert await FoodRecord.filter(user=user).count() == 1  # 同句其他段照常入库


async def test_删输入行不动记录(db, monkeypatch):
    user = await _user(nick="删输入")
    result = pipeline.PipelineResult(
        output=ParseOutput(
            items=[ParsedFood(spoken_name="黄瓜", name="黄瓜(鲜)", grams=100)]
        )
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))
    resp = await api.chat(api.ChatIn(text="吃了根黄瓜100克"), user)
    await _drain(resp)

    await (await Input.get(user=user)).delete()

    food = await FoodRecord.get(user=user)  # raw 是唯一事实源,记录还在
    assert food.input_id is None


# ── 没体重的新用户(2026-07-12 修"第一句想记体重却被拒"死循环) ──────────────


async def _fresh_user(nick="新注册"):
    return await User.create(
        nickname=nick, height_cm=170, sex="female", birth_year=1999
    )


async def test_新用户没体重_第一句记体重_不再被拒(db, monkeypatch):
    user = await _fresh_user()
    result = pipeline.PipelineResult(
        output=ParseOutput(items=[ParsedWeight(weight_kg=68)])
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))

    resp = await api.chat(api.ChatIn(text="今天的体重是68千克"), user)
    body = await _drain(resp)

    assert (await WeightRecord.get(user=user)).weight_kg == 68
    assert (await Input.get(user=user)).status == "ok"
    assert "无法计算" not in body


async def test_新用户没体重_同句带体重和运动_运动照常算消耗(db, monkeypatch):
    from app.ai.schema import ParsedExercise

    from app.models import ExerciseRecord

    user = await _fresh_user(nick="新注册2")
    result = pipeline.PipelineResult(
        output=ParseOutput(
            items=[
                ParsedWeight(weight_kg=68),
                ParsedExercise(name="跑步", duration_min=30),
            ]
        )
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))

    resp = await api.chat(api.ChatIn(text="今天68公斤,跑了30分钟"), user)
    await _drain(resp)

    ex = await ExerciseRecord.get(user=user)
    assert ex.kcal > 0  # 用同句报的体重当场算出消耗
    assert (await Input.get(user=user)).status == "ok"


async def test_新用户没体重_只报运动_该段降级并提示先记体重(db, monkeypatch):
    from app.ai.schema import ParsedExercise

    from app.models import ExerciseRecord

    user = await _fresh_user(nick="新注册3")
    result = pipeline.PipelineResult(
        output=ParseOutput(items=[ParsedExercise(name="跑步", duration_min=30)])
    )
    monkeypatch.setattr(pipeline, "parse_via_triage", _fake_pipeline(result))

    resp = await api.chat(api.ChatIn(text="跑了30分钟"), user)
    body = await _drain(resp)

    assert await ExerciseRecord.filter(user=user).count() == 0  # 没编数,老实没记
    assert "体重" in body  # 回执提示先记一句体重
    assert (await Input.get(user=user)).status == "partial"  # 有一段没记上
