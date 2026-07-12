"""管理员脚本:按昵称重置用户密码(bcrypt 哈希入库)。

两个用途:朋友忘密码找管理员重置;登录上线时给存量用户补密码。
已发的登录令牌不受影响(重置≠踢下线;要踢人删 auth_tokens 行)。

运行:backend 目录下 uv run python scripts/reset_password.py <昵称> <新密码>
"""

import asyncio
import sys

import bcrypt
from tortoise import Tortoise

from app.db import TORTOISE_ORM
from app.models import User


async def main(nickname: str, password: str) -> None:
    if len(password) < 6:
        raise SystemExit("密码最短 6 位")
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        user = await User.get_or_none(nickname=nickname)
        if user is None:
            raise SystemExit(f"没有昵称为「{nickname}」的用户")
        user.password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt()
        ).decode()
        await user.save()
        print(f"已重置「{nickname}」的密码")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法:uv run python scripts/reset_password.py <昵称> <新密码>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
