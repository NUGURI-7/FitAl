"""一次性脚本:给存量用户设定用户名(2026-07-12 用户名/昵称拆分的过渡补齐)。

用户名=登录标识,字母数字下划线 3-20 位,全局唯一,设定后不可改
(接口不提供改名;真要改还是跑这个脚本)。

运行:backend 目录下 PYTHONPATH=. uv run python scripts/set_username.py <用户ID> <用户名>
"""

import asyncio
import re
import sys

from tortoise import Tortoise
from tortoise.exceptions import IntegrityError

from app.db import TORTOISE_ORM
from app.models import User


async def main(user_id: int, username: str) -> None:
    if re.fullmatch(r"[A-Za-z0-9_]{3,20}", username) is None:
        raise SystemExit("用户名只能是字母/数字/下划线,3-20 位")
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise SystemExit(f"没有 ID 为 {user_id} 的用户")
        user.username = username
        try:
            await user.save()
        except IntegrityError:
            raise SystemExit(f"用户名「{username}」已被占用") from None
        print(f"用户 {user_id}(昵称「{user.nickname}」)的用户名已设为「{username}」")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "用法:PYTHONPATH=. uv run python scripts/set_username.py <用户ID> <用户名>"
        )
    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
