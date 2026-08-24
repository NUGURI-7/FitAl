import pytest
import pytest_asyncio
from starlette.requests import Request
from tortoise import Tortoise

from app import ratelimit


def fake_request(
    ip: str = "203.0.113.1", headers: dict[str, str] | None = None
) -> Request:
    """直接调用接口函数的单测用:造一个带来源地址(可另带请求头)的最小请求。"""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
            ],
            "client": (ip, 54321),
        }
    )


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    """限速计数在进程内存里,测试之间必须清干净,否则互相串。"""
    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


@pytest_asyncio.fixture
async def db():
    """单测数据库:内存 SQLite,零外部依赖(双库能力由 Tortoise 提供)。

    仅测试用 generate_schemas(库是一次性的);真实 PG 建表一律走迁移。
    """
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
        use_tz=True,  # 与生产 TORTOISE_ORM 配置保持一致:一律 aware UTC
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
