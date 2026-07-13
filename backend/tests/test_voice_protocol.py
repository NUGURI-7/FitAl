"""语音协议编解码单测:校验打包的字节布局,并自解验证往返(不联网)。"""

import gzip
import json
import struct

from app.voice import protocol


def test_首包按JSON加gzip打包且头字节正确():
    frame = protocol.full_client_request({"a": 1})
    assert frame[0] == 0x11  # 版本1+头长1
    assert (frame[1] >> 4) == 0b0001  # 消息类型=首包
    assert frame[2] == 0x11  # JSON+gzip
    size = struct.unpack(">I", frame[4:8])[0]
    assert gzip.decompress(frame[8 : 8 + size]) == json.dumps({"a": 1}).encode()


def test_音频末包打负包标志而普通包不打():
    assert (protocol.audio_request(b"\x00\x01", is_last=False)[1] & 0x0F) == 0b0000
    assert (protocol.audio_request(b"\x00\x01", is_last=True)[1] & 0x0F) == 0b0010


def test_解析识别结果帧还原文本与定稿标志():
    body = gzip.compress(json.dumps({"result": {"text": "你好"}}).encode())
    frame = (
        bytes([0x11, (0b1001 << 4) | 0b0011, 0x11, 0x00])
        + struct.pack(">i", 3)
        + struct.pack(">I", len(body))
        + body
    )
    out = protocol.parse_response(frame)
    assert out["type"] == "result"
    assert out["payload"]["result"]["text"] == "你好"
    assert out["is_final"] is True
