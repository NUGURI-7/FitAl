"""前端 ↔ 后端 语音通道(WS /voice)。
验登录令牌 → 连豆包 → 两头对倒(前端音频转给豆包,豆包文字回给前端)→ 收尾。
只做语音转文字,不碰记账。
"""

import asyncio
import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models import AuthToken, User
from app.voice.doubao import DoubaoASR, DoubaoASRError

router = APIRouter()

_MAX_SECONDS = 120  # 单条连接安全上限:前端异常没主动关,也不会挂死连接


async def _user_for_token(token: str) -> User | None:
    """登录令牌查表定人(WS 用不了 HTTP 的 Header 依赖,故这里直接查)。"""
    row = await AuthToken.get_or_none(token=token) if token else None
    return await User.get(id=row.user_id) if row else None


@router.websocket("/voice")
async def voice(ws: WebSocket):
    await ws.accept()

    # ① 首条必须是 {"type":"start","token":...},验令牌
    try:
        start = await ws.receive_json()
    except Exception:
        await ws.close()
        return
    if start.get("type") != "start" or not await _user_for_token(
        start.get("token", "")
    ):
        await ws.send_json({"type": "error", "message": "未登录"})
        await ws.close()
        return

    # ② 连豆包;连不上就告诉前端并收摊
    asr = DoubaoASR()
    try:
        await asr.connect()
    except Exception:
        await ws.send_json({"type": "error", "message": "语音服务连接失败"})
        await ws.close()
        return
    await ws.send_json({"type": "ready"})

    # ③ 两头对倒
    async def frontend_to_doubao():
        """前端来的:二进制=音频段;{"type":"stop"}=说完→给豆包补个末包。"""
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(msg.get("code", 1000))
            if msg.get("bytes") is not None:
                await asr.send_audio(msg["bytes"], is_last=False)
            elif msg.get("text") and json.loads(msg["text"]).get("type") == "stop":
                await asr.send_audio(b"", is_last=True)
                return

    async def doubao_to_frontend():
        """豆包来的:逐条识别结果发前端;定稿后发 done。"""
        async for r in asr.results():
            await ws.send_json(
                {"type": "result", "text": r["text"], "is_final": r["is_final"]}
            )
        await ws.send_json({"type": "done"})

    # ④ 收尾:定稿正常结束 / 前端断开 / 豆包报错 / 超时,末了一律关两条连接
    try:
        async with asyncio.timeout(_MAX_SECONDS):
            await asyncio.gather(frontend_to_doubao(), doubao_to_frontend())
    except WebSocketDisconnect:
        pass  # 前端断开=正常结束
    except DoubaoASRError as e:
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "message": f"识别出错:{e.message}"})
    except (TimeoutError, asyncio.TimeoutError):
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "message": "超时结束"})
    finally:
        await asr.close()
        with contextlib.suppress(Exception):
            await ws.close()
