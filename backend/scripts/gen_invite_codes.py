"""管理员脚本:生成邀请码(一人一码,注册消耗即作废)。

运行:backend 目录下 uv run python scripts/gen_invite_codes.py [数量,默认1]
生成的码直接打印,微信发给朋友即可。
"""

import asyncio
import secrets
import sys

from tortoise import Tortoise

from app.db import TORTOISE_ORM
from app.models import InviteCode

# 8 位大写字母数字,剔除 0/O/1/I 等易混字符,口头/微信传都不易抄错
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


async def main(count: int) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    for _ in range(count):
        row = await InviteCode.create(code=_new_code())
        print(row.code)
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
