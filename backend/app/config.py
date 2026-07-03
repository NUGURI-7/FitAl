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

    # ==================== LLM ====================
    DEEPSEEK_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
