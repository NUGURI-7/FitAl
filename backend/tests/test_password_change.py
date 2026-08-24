"""改密码(2026-08-23 用户定):旧密码即身份证明,不接外部通道;
改完吊销该用户其他令牌、保留当前这台;旧密码连错 5 次锁 5 分钟。"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import api
from app.models import AuthToken, InviteCode, User
from tests.conftest import fake_request


async def _new_user(username="xinpengyou", password="secret6"):
    await InviteCode.create(code=f"CODE-{username}")
    out = await api.register(
        api.RegisterIn(
            invite_code=f"CODE-{username}",
            username=username,
            nickname="新朋友",
            password=password,
            height_cm=170,
            sex="female",
            birth_year=1999,
        ),
        fake_request(),
    )
    return out["token"]


async def _change(token, old="secret6", new="newpass6"):
    user = await api.current_user(f"Bearer {token}")
    return await api.change_password(
        api.PasswordChangeIn(old_password=old, new_password=new),
        f"Bearer {token}",
        user,
    )


async def test_改密码_旧密码对_新密码即刻生效(db):
    token = await _new_user()
    await _change(token)

    with pytest.raises(HTTPException):  # 旧密码作废
        await api.login(
            api.LoginIn(username="xinpengyou", password="secret6"), fake_request()
        )
    assert (
        await api.login(
            api.LoginIn(username="xinpengyou", password="newpass6"), fake_request()
        )
    )["user_id"]


async def test_改密码_旧密码不对_拒绝且密码不动(db):
    token = await _new_user()
    with pytest.raises(HTTPException) as e:
        await _change(token, old="猜的密码")
    assert e.value.status_code == 403

    user = await User.get(username="xinpengyou")
    assert api._verify_password("secret6", user.password_hash)  # 原密码没被改


async def test_改密码_其他设备被踢下线_当前这台还在(db):
    phone = await _new_user()
    web = (
        await api.login(
            api.LoginIn(username="xinpengyou", password="secret6"), fake_request()
        )
    )["token"]
    pad = (
        await api.login(
            api.LoginIn(username="xinpengyou", password="secret6"), fake_request()
        )
    )["token"]
    assert await AuthToken.filter(token__in=[phone, web, pad]).count() == 3

    out = await _change(phone)
    assert out["revoked_devices"] == 2

    assert await api.current_user(f"Bearer {phone}")  # 当前这台照常
    for gone in (web, pad):
        with pytest.raises(HTTPException) as e:
            await api.current_user(f"Bearer {gone}")
        assert e.value.status_code == 401


async def test_改密码_新密码短于六位_直接不给提交(db):
    with pytest.raises(ValidationError):
        api.PasswordChangeIn(old_password="secret6", new_password="12345")


async def test_改密码_旧密码连错五次后锁定(db):
    token = await _new_user()
    for _ in range(5):
        with pytest.raises(HTTPException) as e:
            await _change(token, old="猜的密码")
        assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        await _change(token, old="secret6")  # 锁定期内旧密码对也拒
    assert e.value.status_code == 429


async def test_改密码_两个人各锁各的(db):
    me = await _new_user()
    other = await _new_user(username="linju")
    for _ in range(5):
        with pytest.raises(HTTPException):
            await _change(me, old="猜的密码")

    assert (await _change(other))["status"] == "ok"  # 邻居不受牵连
