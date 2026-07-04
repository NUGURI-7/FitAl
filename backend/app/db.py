from app.config import settings

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": settings.PG_HOST,
                "port": settings.PG_PORT,
                "user": settings.PG_USER,
                "password": settings.PG_PASSWORD,
                "database": settings.PG_DATABASE,
            },
        },
    },
    "apps": {
        "models": {
            "models": ["app.models"],
            "default_connection": "default",
            "migrations": "app.migrations",
        },
    },
    # 存储一律 aware UTC(timestamptz);本地时间只在展示/注入 prompt 时转换
    "use_tz": True,
    "timezone": settings.TIMEZONE,
}
