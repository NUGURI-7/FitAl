"""豆包流式语音识别 · WebSocket 二进制协议(纯编解码,不联网)。

每帧 = 4字节头 + [4字节序号] + 4字节载荷长度(大端) + 载荷。
载荷:首包=识别参数 JSON(gzip),音频包=裸 PCM(gzip)。
逐字节布局照火山官方文档,已由连通试验实测通过。
"""

import gzip
import json
import struct

# 消息类型
_FULL_CLIENT = 0b0001  # 端上:带参数的首包
_AUDIO_ONLY = 0b0010  # 端上:音频包
_SERVER_RESPONSE = 0b1001  # 服务端:识别结果
_SERVER_ERROR = 0b1111  # 服务端:错误

# 标志位(末包用负包标志告诉豆包"说完了")
_FLAG_NONE = 0b0000
_FLAG_LAST = 0b0010

# 序列化 / 压缩
_JSON = 0b0001
_RAW = 0b0000
_GZIP = 0b0001


def _header(message_type, flags, serialization, compression):
    return bytes(
        [
            (0b0001 << 4) | 0b0001,  # 版本1、头长1(=4字节)
            (message_type << 4) | flags,
            (serialization << 4) | compression,
            0x00,  # 保留
        ]
    )


def full_client_request(config: dict) -> bytes:
    """首包:把识别参数打包成一帧。"""
    payload = gzip.compress(json.dumps(config).encode("utf-8"))
    return (
        _header(_FULL_CLIENT, _FLAG_NONE, _JSON, _GZIP)
        + struct.pack(">I", len(payload))
        + payload
    )


def audio_request(audio: bytes, is_last: bool) -> bytes:
    """音频包:一小段裸 PCM;末包打负包标志。"""
    flags = _FLAG_LAST if is_last else _FLAG_NONE
    payload = gzip.compress(audio)
    return (
        _header(_AUDIO_ONLY, flags, _RAW, _GZIP)
        + struct.pack(">I", len(payload))
        + payload
    )


def parse_response(data: bytes) -> dict:
    """解服务端一帧:
    {"type":"result", "payload":{...}, "is_final":bool}  识别结果
    {"type":"error",  "code":int, "message":str}         错误
    {"type":"unknown","message_type":int}                其他
    """
    header_size = (data[0] & 0x0F) * 4
    message_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    compression = data[2] & 0x0F
    offset = header_size
    if flags & 0b0001:  # 带 4 字节序号则跳过
        offset += 4
    if message_type == _SERVER_RESPONSE:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        payload = data[offset : offset + size]
        if compression == _GZIP:
            payload = gzip.decompress(payload)
        return {
            "type": "result",
            "payload": json.loads(payload),
            "is_final": flags == 0b0011,
        }
    if message_type == _SERVER_ERROR:
        code = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        msg = data[offset : offset + size].decode("utf-8", "replace")
        return {"type": "error", "code": code, "message": msg}
    return {"type": "unknown", "message_type": message_type}
