from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """
    Single source of truth for runtime config (Python 3.13 + pydantic-settings).
    """

    SQLALCHEMY_DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"
    SQL_ECHO: bool = False

    # Production-like process settings (used by `python -m backend.main`)
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000
    UVICORN_WORKERS: int = 4
    # True only for local single-process debugging — never with --workers
    UVICORN_RELOAD: bool = False

    USE_REDIS: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    # Keep this modest: each uvicorn worker creates its own pool
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: float = 5.0

    CACHE_TTL_SECONDS: int = 3600
    RATE_LIMIT_BUY_PER_MINUTE: int = 10
    STOCK_LOCK_TTL_MS: int = 5_000

    PURCHASE_STREAM: str = "stream:purchases"
    PURCHASE_CHANNEL: str = "channel:purchases"
    CARD_CHANNEL: str = "channel:card"
    RECENT_PURCHASES_ZSET: str = "zset:recent_purchases"
    RECENT_PURCHASES_MAX: int = 100

    # Only one uvicorn worker may run the stream consumer
    CONSUMER_LEADER_LOCK_KEY: str = "lock:purchase-stream-consumer"
    CONSUMER_LEADER_LOCK_TTL_MS: int = 30_000

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
