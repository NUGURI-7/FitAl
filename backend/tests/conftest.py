import pytest_asyncio
from tortoise import Tortoise


@pytest_asyncio.fixture
async def db():
    """单测数据库:内存 SQLite,零外部依赖(双库能力由 Tortoise 提供)。

    仅测试用 generate_schemas(库是一次性的);真实 PG 建表一律走迁移。
    """
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
