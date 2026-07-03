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

    # ==================== LLM(任意 OpenAI 兼容端点)====================
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""  # 本地部署无鉴权时留空
    LLM_EXTRA_BODY: str = ""  # 端点私有参数(JSON 字符串),如 DeepSeek 关思考模式

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
