from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import router
from app.db import TORTOISE_ORM
from app.voice.routes import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=TORTOISE_ORM):
        yield


app = FastAPI(title="FitAl", lifespan=lifespan)
app.include_router(router)
app.include_router(voice_router)

# ── 前端静态资源(生产环境:web/dist 存在时挂载;开发环境自动跳过)──────────
# 镜像里 web/dist 与 backend 同级(/app/web/dist),开发期为仓库根 web/dist
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
