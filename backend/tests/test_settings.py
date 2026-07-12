"""设置页接口:身体档案读改 + 自定义食物查删 + AI 记忆查删。
改档案不回算已存记录,派生数字读时现算;删自定义食物只影响以后的查表;
删记忆即停止注入解析 prompt。"""

import pytest
from fastapi import HTTPException

from app import api
from app.models import AiMemory, User, UserFood


async def _user(nick="档案测试"):
    return await User.create(nickname=nick, height_cm=178, sex="male", birth_year=1997)


async def test_读档案_返回全部档案字段含只读ID(db):
    user = await _user()
    out = await api.get_user(user)
    assert out == {
        "id": user.id,
        "nickname": "档案测试",
        "height_cm": 178,
        "sex": "male",
        "birth_year": 1997,
    }


async def test_认人_无令牌或坏令牌一律401(db):
    with pytest.raises(HTTPException) as e1:
        await api.current_user(authorization="")
    with pytest.raises(HTTPException) as e2:
        await api.current_user(authorization="Bearer 瞎编的令牌")
    assert e1.value.status_code == e2.value.status_code == 401


async def test_改档案_只改身高_其余字段不动(db):
    user = await _user()
    out = await api.patch_user(api.UserPatch(height_cm=180.5), user)
    assert out["height_cm"] == 180.5
    assert out["nickname"] == "档案测试"
    assert out["sex"] == "male"
    assert out["birth_year"] == 1997
    await user.refresh_from_db()
    assert user.height_cm == 180.5


async def test_改档案_可同时改多个字段(db):
    user = await _user()
    out = await api.patch_user(
        api.UserPatch(nickname="新名字", sex="female", birth_year=2000), user
    )
    assert out["nickname"] == "新名字"
    assert out["sex"] == "female"
    assert out["birth_year"] == 2000


async def test_改昵称_与他人重名报409(db):
    await _user(nick="占位者")
    user = await _user(nick="本人")
    with pytest.raises(HTTPException) as e:
        await api.patch_user(api.UserPatch(nickname="占位者"), user)
    assert e.value.status_code == 409


async def test_改档案_空请求体报422(db):
    user = await _user()
    with pytest.raises(HTTPException) as e:
        await api.patch_user(api.UserPatch(), user)
    assert e.value.status_code == 422


async def test_自定义食物列表_按更新时间倒序且只看自己的(db):
    user = await _user()
    other = await _user(nick="别人")
    await UserFood.create(user=user, name="蛋白粉", kcal=400)
    await UserFood.create(user=user, name="希腊酸奶", kcal=59, protein=10.3)
    await UserFood.create(user=other, name="别人的食物", kcal=100)

    out = await api.list_user_foods(user)
    names = [f["name"] for f in out["foods"]]
    assert names == ["希腊酸奶", "蛋白粉"]  # 后记的在前,看不到别人的
    assert out["foods"][0]["kcal"] == 59
    assert out["foods"][0]["protein"] == 10.3


async def test_删别人的自定义食物_如同不存在报404(db):
    user = await _user()
    other = await _user(nick="别人")
    food = await UserFood.create(user=other, name="别人的食物", kcal=100)
    with pytest.raises(HTTPException) as e:
        await api.delete_user_food(food.id, user)
    assert e.value.status_code == 404
    assert await UserFood.get_or_none(id=food.id) is not None  # 没被误删


async def test_删自定义食物_记录消失(db):
    user = await _user()
    food = await UserFood.create(user=user, name="蛋白粉", kcal=400)
    out = await api.delete_user_food(food.id, user)
    assert out == {"deleted": food.id}
    assert await UserFood.get_or_none(id=food.id) is None


async def test_删自定义食物_不存在报404(db):
    user = await _user()
    with pytest.raises(HTTPException) as e:
        await api.delete_user_food(99999, user)
    assert e.value.status_code == 404


async def test_记忆列表_按更新时间倒序且只看自己的(db):
    user = await _user()
    other = await _user(nick="别人")
    await AiMemory.create(user=user, kind="habit", content="一勺是30克")
    await AiMemory.create(user=user, kind="correction", content="修正过猪脚饭估算")
    await AiMemory.create(user=other, kind="alias", content="别人的记忆")

    out = await api.list_memories(user)
    contents = [m["content"] for m in out["memories"]]
    assert contents == ["修正过猪脚饭估算", "一勺是30克"]  # 新的在前,看不到别人的
    assert out["memories"][0]["kind"] == "correction"


async def test_删别人的记忆_如同不存在报404(db):
    user = await _user()
    other = await _user(nick="别人")
    memory = await AiMemory.create(user=other, kind="habit", content="别人的记忆")
    with pytest.raises(HTTPException) as e:
        await api.delete_memory(memory.id, user)
    assert e.value.status_code == 404
    assert await AiMemory.get_or_none(id=memory.id) is not None  # 没被误删


async def test_删记忆_记录消失(db):
    user = await _user()
    memory = await AiMemory.create(user=user, kind="habit", content="一勺是30克")
    out = await api.delete_memory(memory.id, user)
    assert out == {"deleted": memory.id}
    assert await AiMemory.get_or_none(id=memory.id) is None


async def test_删记忆_不存在报404(db):
    user = await _user()
    with pytest.raises(HTTPException) as e:
        await api.delete_memory(99999, user)
    assert e.value.status_code == 404
