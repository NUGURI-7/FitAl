"""记忆链路:"记住"条目落库、解析注入、每日巩固触发与整层替换。"""

from datetime import datetime, timedelta

from tortoise import timezone

from app import api
from app.ai import parser
from app.ai.schema import MemoryItem, ParsedMemory, ParsedUserFoodDef, ParseOutput
from app.models import AiMemory, User, UserFood

PROFILE = parser.Profile(weight_kg=70, height_cm=178, sex="male", birth_year=1997)


async def _user(nick="记忆测试"):
    return await User.create(nickname=nick, height_cm=178, sex="male", birth_year=1997)


def test_解析透传_记住条目不经计算原样传递():
    items = [
        ParsedUserFoodDef(name="老三样", grams=100, kcal=520),
        ParsedMemory(kind="alias", content="用户说鸡胸指鸡胸脯肉"),
    ]
    records = parser.build_records(
        ParseOutput(items=items), profile=PROFILE, now=datetime(2026, 7, 4, 12)
    )
    assert records == items


async def test_记住自定义食物_按克数换算成每100克入库(db):
    user = await _user()
    item = ParsedUserFoodDef(name="老三样", grams=50, kcal=260, protein=22.5)
    await api.persist_records(user, "记住老三样50克260千卡", [item])
    [row] = await UserFood.filter(user=user)
    assert row.kcal == 520  # 260千卡/50克 → 每100克520千卡,换算归代码
    assert row.protein == 45
    assert row.form is None  # 形态列可空,没说不填


async def test_记住自定义食物_重复记住即更新(db):
    user = await _user()
    await api.persist_records(
        user,
        "记住老三样100克520千卡",
        [ParsedUserFoodDef(name="老三样", grams=100, kcal=520)],
    )
    await api.persist_records(
        user,
        "记住老三样100克550千卡",
        [ParsedUserFoodDef(name="老三样", grams=100, kcal=550)],
    )
    rows = await UserFood.filter(user=user)
    assert len(rows) == 1
    assert rows[0].kcal == 550


async def test_记住缺克数_不入库且回执提示补克数(db):
    user = await _user()
    item = ParsedUserFoodDef(name="老三样", kcal=520)  # 用户没给克数
    cards = await api.persist_records(user, "记住老三样520千卡", [item])
    assert cards == []
    assert await UserFood.filter(user=user).count() == 0
    assert "补上克数" in api.compose_reply([item])


async def test_记住叫法_落记忆表(db):
    user = await _user()
    item = ParsedMemory(kind="alias", content="用户说鸡胸指鸡胸脯肉")
    cards = await api.persist_records(user, "以后我说鸡胸就是鸡胸脯肉", [item])
    rows = await AiMemory.filter(user=user)
    assert len(rows) == 1
    assert rows[0].kind == "alias"
    assert cards[0]["type"] == "memory"


async def _fake_consolidate(calls: list):
    async def fake(rows):
        calls.append(rows)
        return [MemoryItem(kind="alias", content="合并后的一条")]

    return fake


async def test_巩固_不足两条不触发(db, monkeypatch):
    user = await _user()
    await AiMemory.create(user=user, kind="alias", content="仅一条")
    calls = []
    monkeypatch.setattr(parser, "consolidate_memories", await _fake_consolidate(calls))
    rows = await AiMemory.filter(user=user).order_by("updated_at")
    await api.maybe_consolidate_memories(user, timezone.now() + timedelta(days=1), rows)
    assert calls == []


async def test_巩固_今天动过不触发(db, monkeypatch):
    user = await _user()
    await AiMemory.create(user=user, kind="alias", content="一")
    await AiMemory.create(user=user, kind="habit", content="二")
    calls = []
    monkeypatch.setattr(parser, "consolidate_memories", await _fake_consolidate(calls))
    rows = await AiMemory.filter(user=user).order_by("updated_at")
    await api.maybe_consolidate_memories(user, timezone.now(), rows)  # 刚建即"今天"
    assert calls == []


async def test_巩固_触发时整层替换(db, monkeypatch):
    user = await _user()
    await AiMemory.create(user=user, kind="alias", content="一")
    await AiMemory.create(user=user, kind="alias", content="二")
    calls = []
    monkeypatch.setattr(parser, "consolidate_memories", await _fake_consolidate(calls))
    rows = await AiMemory.filter(user=user).order_by("updated_at")
    await api.maybe_consolidate_memories(user, timezone.now() + timedelta(days=1), rows)
    assert len(calls) == 1
    remaining = await AiMemory.filter(user=user)
    assert [r.content for r in remaining] == ["合并后的一条"]


async def test_巩固_AI返回空清单不执行删除(db, monkeypatch):
    user = await _user()
    await AiMemory.create(user=user, kind="alias", content="一")
    await AiMemory.create(user=user, kind="alias", content="二")

    async def empty(rows):
        return []

    monkeypatch.setattr(parser, "consolidate_memories", empty)
    rows = await AiMemory.filter(user=user).order_by("updated_at")
    await api.maybe_consolidate_memories(user, timezone.now() + timedelta(days=1), rows)
    assert await AiMemory.filter(user=user).count() == 2


async def test_巩固_LLM失败静默跳过不影响主链路(db, monkeypatch):
    user = await _user()
    await AiMemory.create(user=user, kind="alias", content="一")
    await AiMemory.create(user=user, kind="alias", content="二")

    async def boom(rows):
        raise RuntimeError("端点宕机")

    monkeypatch.setattr(parser, "consolidate_memories", boom)
    rows = await AiMemory.filter(user=user).order_by("updated_at")
    await api.maybe_consolidate_memories(
        user, timezone.now() + timedelta(days=1), rows
    )  # 不抛异常即通过
    assert await AiMemory.filter(user=user).count() == 2
