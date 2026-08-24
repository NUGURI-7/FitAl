"""登录/注册失败限速(2026-08-23 用户定):同一用户名连续失败 5 次锁 5 分钟,
同一来源 IP 每 15 分钟最多 20 次失败,注册按 IP 每小时最多 10 次邀请码猜测。
计数在进程内存里,成功登录即清零。"""

import pytest
from fastapi import HTTPException

from app import api, ratelimit
from app.models import InviteCode
from tests.conftest import fake_request


def _register_body(**overrides):
    body = dict(
        invite_code="CODE-1",
        username="xinpengyou",
        nickname="新朋友",
        password="secret6",
        height_cm=170,
        sex="female",
        birth_year=1999,
    )
    body.update(overrides)
    return api.RegisterIn(**body)


async def _login(username="xinpengyou", password="secret6", ip="203.0.113.1"):
    return await api.login(
        api.LoginIn(username=username, password=password), fake_request(ip)
    )


# ── 策略本身(纯函数,时间可控)────────────────────────────────────────


def test_未达上限时不限速():
    for _ in range(4):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    assert ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=0) == 0


def test_失败满五次后被限且给出剩余秒数():
    for _ in range(5):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    wait = ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=0)
    assert 0 < wait <= 301  # 5 分钟量级


def test_锁定五分钟后自动解封():
    for _ in range(5):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    assert ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=299) > 0
    assert ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=301) == 0


def test_窗口内的旧失败会滑出不再计数():
    for _ in range(4):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    # 第 5 次发生在 5 分钟之后:前 4 次已滑出窗口,不该凑成 5 次
    ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=400)
    assert ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=400) == 0


def test_清零后重新开始计数():
    for _ in range(5):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    ratelimit.clear("login_user", "a")
    assert ratelimit.retry_after("login_user", "a", ratelimit.LOGIN_USER, now=0) == 0


def test_不同键各算各的():
    for _ in range(5):
        ratelimit.record_failure("login_user", "a", ratelimit.LOGIN_USER, now=0)
    assert ratelimit.retry_after("login_user", "b", ratelimit.LOGIN_USER, now=0) == 0


# ── 接到登录/注册接口上 ────────────────────────────────────────────


async def test_登录连错五次_第六次改回请稍后再试(db):
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body(), fake_request())

    for _ in range(5):
        with pytest.raises(HTTPException) as e:
            await _login(password="wrong-1")
        assert e.value.status_code == 401  # 前五次照旧是"用户名或密码不对"

    with pytest.raises(HTTPException) as e:
        await _login(password="wrong-1")
    assert e.value.status_code == 429
    assert "再试" in e.value.detail
    assert e.value.headers["Retry-After"].isdigit()


async def test_被限期间_就算密码是对的也拒(db):
    """锁定期内直接拒,不再核验密码——这才挡得住暴力破解。"""
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body(), fake_request())
    for _ in range(5):
        with pytest.raises(HTTPException):
            await _login(password="wrong-1")

    with pytest.raises(HTTPException) as e:
        await _login(password="secret6")
    assert e.value.status_code == 429


async def test_登录成功清零_手滑输错几次不留痕(db):
    await InviteCode.create(code="CODE-1")
    await api.register(_register_body(), fake_request())
    for _ in range(4):
        with pytest.raises(HTTPException):
            await _login(password="wrong-1")

    assert (await _login())["user_id"]  # 第五次输对,正常放行

    for _ in range(4):  # 计数已清零,又能错四次
        with pytest.raises(HTTPException) as e:
            await _login(password="wrong-1")
        assert e.value.status_code == 401


async def test_换个用户名不受别人的失败牵连(db):
    await InviteCode.create(code="CODE-1")
    await InviteCode.create(code="CODE-2")
    await api.register(_register_body(), fake_request())
    await api.register(
        _register_body(invite_code="CODE-2", username="linju", nickname="邻居"),
        fake_request(),
    )
    for _ in range(6):
        with pytest.raises(HTTPException):
            await _login(password="wrong-1")

    assert (await _login(username="linju"))["user_id"]  # 邻居照常登录


async def test_同一来源横扫多个账号_满二十次被拒(db):
    """按用户名各算各的,但按 IP 汇总能挡住"一个来源换着账号试"。"""
    for i in range(20):
        with pytest.raises(HTTPException) as e:
            await _login(username=f"buc{i}", password="x123456")
        assert e.value.status_code == 401

    with pytest.raises(HTTPException) as e:
        await _login(username="haimeishiguo", password="x123456")
    assert e.value.status_code == 429


async def test_注册邀请码猜十次后被拒(db):
    for _ in range(10):
        with pytest.raises(HTTPException) as e:
            await api.register(_register_body(invite_code="瞎猜的"), fake_request())
        assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        await api.register(_register_body(invite_code="还瞎猜"), fake_request())
    assert e.value.status_code == 429


async def test_注册成功不受限速影响(db):
    await InviteCode.create(code="CODE-1")
    for _ in range(9):
        with pytest.raises(HTTPException):
            await api.register(_register_body(invite_code="瞎猜的"), fake_request())

    assert (await api.register(_register_body(), fake_request()))["user_id"]


# ── 来源 IP 的取法(2026-08-23:线上是 访客→Cloudflare→Caddy→本服务)────


def test_优先用_cloudflare_填的地址_访客伪造的转发头不算():
    req = fake_request(
        "10.0.0.1",
        {"cf-connecting-ip": "1.1.1.1", "x-forwarded-for": "伪造的, 10.0.0.1"},
    )
    assert api._client_ip(req) == "1.1.1.1"


def test_没有_cloudflare_头时退回通用转发头的第一个地址():
    req = fake_request("10.0.0.1", {"x-forwarded-for": "2.2.2.2, 10.0.0.1"})
    assert api._client_ip(req) == "2.2.2.2"


def test_两个头都没有时用直连地址():
    assert api._client_ip(fake_request("3.3.3.3")) == "3.3.3.3"
