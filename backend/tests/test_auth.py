"""登录/注册(契约 2026-07-12):令牌存库不用 JWT,认人靠查表。
邀请码一人一码用完作废;密码 bcrypt 单向哈希最短 6 位;
登录失败统一一句话;一用户多令牌,退出只删本枚。"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import api
from app.models import AuthToken, InviteCode, User


def _register_body(**overrides):
    body = dict(
        invite_code="CODE-1",
        nickname="新朋友",
        password="secret6",
        height_cm=170,
        sex="female",
        birth_year=1999,
    )
    body.update(overrides)
    return api.RegisterIn(**body)


async def test_注册_有效邀请码_建用户发令牌_码作废(db):
    code = await InviteCode.create(code="CODE-1")
    out = await api.register(_register_body())

    user = await User.get(nickname="新朋友")
    assert out["user_id"] == user.id
    assert (await AuthToken.get(token=out["token"])).user_id == user.id  # 当场发令牌
    await code.refresh_from_db()
    assert code.used_at is not None and code.used_by_id == user.id  # 码作废并留痕


async def test_注册_密码不存明文_单向哈希可验证(db):
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body())
    user = await User.get(nickname="新朋友")
    assert user.password_hash != "secret6"
    assert api._verify_password("secret6", user.password_hash)
    assert not api._verify_password("wrong-1", user.password_hash)


async def test_注册_邀请码不存在_403(db):
    with pytest.raises(HTTPException) as e:
        await api.register(_register_body(invite_code="没这个码"))
    assert e.value.status_code == 403


async def test_注册_邀请码已被用过_403(db):
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body())
    with pytest.raises(HTTPException) as e:
        await api.register(_register_body(nickname="第二人"))
    assert e.value.status_code == 403


async def test_注册_昵称重名_409且不消耗邀请码(db):
    await User.create(nickname="占位者", height_cm=178, sex="male", birth_year=1997)
    code = await InviteCode.create(code="CODE-1")
    with pytest.raises(HTTPException) as e:
        await api.register(_register_body(nickname="占位者"))
    assert e.value.status_code == 409
    await code.refresh_from_db()
    assert code.used_at is None  # 注册没成,码还能再用


async def test_注册_密码不足6位_进不了门(db):
    with pytest.raises(ValidationError):
        _register_body(password="12345")


async def test_登录_密码正确_发新令牌_与注册令牌并存(db):
    await InviteCode.create(code="CODE-1")
    first = await api.register(_register_body())
    second = await api.login(api.LoginIn(nickname="新朋友", password="secret6"))
    assert second["token"] != first["token"]  # 多设备各持一枚
    assert await AuthToken.all().count() == 2


async def test_登录_密码错或用户不存在_统一401同一句话(db):
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body())
    with pytest.raises(HTTPException) as e1:
        await api.login(api.LoginIn(nickname="新朋友", password="wrong-1"))
    with pytest.raises(HTTPException) as e2:
        await api.login(api.LoginIn(nickname="查无此人", password="secret6"))
    assert e1.value.status_code == e2.value.status_code == 401
    assert e1.value.detail == e2.value.detail  # 不给撞库者线索


async def test_登录_存量用户没设密码_401(db):
    await User.create(nickname="老用户", height_cm=178, sex="male", birth_year=1997)
    with pytest.raises(HTTPException) as e:
        await api.login(api.LoginIn(nickname="老用户", password="secret6"))
    assert e.value.status_code == 401


async def test_退出登录_只删本枚令牌_其他设备不掉线(db):
    await InviteCode.create(code="CODE-1")
    phone = await api.register(_register_body())
    web = await api.login(api.LoginIn(nickname="新朋友", password="secret6"))
    await api.logout(authorization=f"Bearer {phone['token']}")
    assert await AuthToken.get_or_none(token=phone["token"]) is None
    assert await AuthToken.get_or_none(token=web["token"]) is not None


async def test_退出登录_令牌已不存在_幂等成功(db):
    out = await api.logout(authorization="Bearer 不存在的令牌")
    assert out == {"status": "ok"}


async def test_认人_有效令牌_返回本人(db):
    await InviteCode.create(code="CODE-1")
    out = await api.register(_register_body())
    user = await api.current_user(authorization=f"Bearer {out['token']}")
    assert user.id == out["user_id"] and user.nickname == "新朋友"
