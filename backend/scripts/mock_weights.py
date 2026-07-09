"""一次性脚本:清空演示用户(id=1)体重记录,插入 7/3→7/8 模拟下降曲线(70→68kg)。

创建时间字段是自动落"现在"的,插入后需再回写成目标日期。
运行:backend 目录下 uv run python scripts/mock_weights.py
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from tortoise import Tortoise

from app.db import TORTOISE_ORM
from app.models import WeightRecord

CST = ZoneInfo("Asia/Shanghai")
USER_ID = 1

# 先慢后快再放缓的非线性下降
POINTS = [
    (datetime(2026, 7, 3, 8, 5, tzinfo=CST), 70.0),
    (datetime(2026, 7, 4, 8, 12, tzinfo=CST), 69.7),
    (datetime(2026, 7, 5, 8, 2, tzinfo=CST), 69.2),
    (datetime(2026, 7, 6, 8, 20, tzinfo=CST), 68.6),
    (datetime(2026, 7, 7, 8, 15, tzinfo=CST), 68.2),
    (datetime(2026, 7, 8, 8, 10, tzinfo=CST), 68.0),
]


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    deleted = await WeightRecord.filter(user_id=USER_ID).delete()
    for at, kg in POINTS:
        rec = await WeightRecord.create(user_id=USER_ID, weight_kg=kg)
        await WeightRecord.filter(id=rec.id).update(created_at=at)
    rows = await WeightRecord.filter(user_id=USER_ID).order_by("created_at")
    print(f"已删 {deleted} 条,插入 {len(POINTS)} 条:")
    for r in rows:
        print(f"  {r.created_at.astimezone(CST):%m-%d %H:%M}  {r.weight_kg}kg")
    await Tortoise.close_connections()


asyncio.run(main())
