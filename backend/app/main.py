from contextlib import asynccontextmanager

from fastapi import FastAPI
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
