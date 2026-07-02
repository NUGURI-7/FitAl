from fastapi import APIRouter
from tortoise import Tortoise

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # 校验 DB 连通,连不上直接 500
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT 1")
    return {"status": "ok"}
