"""豆包客户端:管理一条到豆包的连接——发参数、送音频、收识别结果。
一条连接 = 一次长按说话。底层字节活儿交给 protocol,这里只管流程。
"""

import uuid

import websockets

from app.config import settings
from app.voice import protocol

# 固定的识别参数:16k/单声道 PCM,开数字规范化(两百→200)+ 标点 + 分句定稿
_CONFIG = {
    "user": {"uid": "fital"},
    "audio": {"format": "pcm", "rate": 16000, "bits": 16, "channel": 1},
    "request": {
        "model_name": "bigmodel",
        "enable_itn": True,
        "enable_punc": True,
        "show_utterances": True,
        "result_type": "full",
    },
}


class DoubaoASRError(Exception):
    """豆包回了错误帧。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class DoubaoASR:
    def __init__(self):
        self._ws = None

    async def connect(self):
        """连上豆包,并把识别参数作为首包发出去。"""
        headers = {
            "X-Api-Key": settings.DOUBAO_ASR_API_KEY,
            "X-Api-Resource-Id": settings.DOUBAO_ASR_RESOURCE_ID,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Sequence": "-1",
        }
        self._ws = await websockets.connect(
            settings.DOUBAO_ASR_WS_URL, additional_headers=headers, max_size=None
        )
        await self._ws.send(protocol.full_client_request(_CONFIG))

    async def send_audio(self, chunk: bytes, is_last: bool):
        """送一小段音频;is_last=True 表示这是最后一段。"""
        await self._ws.send(protocol.audio_request(chunk, is_last))

    async def results(self):
        """逐帧产出识别结果 {"text":..., "is_final":...};收到定稿即结束。
        豆包回错误帧则抛 DoubaoASRError。"""
        async for frame in self._ws:
            parsed = protocol.parse_response(frame)
            if parsed["type"] == "result":
                text = (parsed["payload"].get("result") or {}).get("text", "")
                yield {"text": text, "is_final": parsed["is_final"]}
                if parsed["is_final"]:
                    return
            elif parsed["type"] == "error":
                raise DoubaoASRError(parsed["code"], parsed["message"])

    async def close(self):
        """挂断。"""
        if self._ws is not None:
            await self._ws.close()
