from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → parents[1] = backend/
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # ==================== PostgreSQL(云端,分字段见 .env)====================
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = ""
    PG_DATABASE: str = "fital"

    # ==================== 时区(展示/给 LLM 的本地时间;存储一律 UTC)====================
    TIMEZONE: str = "Asia/Shanghai"

    # ==================== LLM(任意 OpenAI 兼容端点)====================
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""  # 本地部署无鉴权时留空
    LLM_EXTRA_BODY: str = ""  # 端点私有参数(JSON 字符串),如 DeepSeek 关思考模式

    # ==================== 豆包流式语音识别(火山引擎 ASR,新版 API Key)====================
    DOUBAO_ASR_API_KEY: str = ""  # 新版控制台 API Keys 页获取,只此一项必填
    DOUBAO_ASR_RESOURCE_ID: str = "volc.seedasr.sauc.duration"  # 2.0 小时版
    DOUBAO_ASR_WS_URL: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
