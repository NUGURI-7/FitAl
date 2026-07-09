"""IDE 本地启动入口:在 PyCharm 里直接 Run 本文件即可起后端。

等价于命令行的 `uv run uvicorn app.main:app --reload`;
host 绑 0.0.0.0 是为了手机(iOS 开发期)能从局域网访问。
生产/命令行仍走 uvicorn CLI,本文件只是开发便利。
"""

from pathlib import Path

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir=str(Path(__file__).parent),
    )
