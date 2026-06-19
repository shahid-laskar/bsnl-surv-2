"""
app/core/config.py
All application settings loaded from environment variables.
No secret, URL, or key has a hardcoded default — must be in .env.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars (e.g. Docker injected ones)
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Sarvanetra"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/db
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_echo: bool = False  # Set True to log SQL queries

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str  # redis://redis:6379/0

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret_key: str  # Must match Kong consumer secret
    jwt_algorithm: str = "HS256"
    jwt_key: str  # Must match Kong consumer key (iss claim)
    jwt_access_token_expire_minutes: int = 60
    jwt_stream_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # ── Kong Admin ───────────────────────────────────────────────────────────
    kong_admin_url: str = "http://kong:8001"

    # ── Kafka ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "kafka:9092"

    # ── MinIO ────────────────────────────────────────────────────────────────
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_recordings_bucket: str = "recordings"
    minio_snapshots_bucket: str = "snapshots"
    minio_secure: bool = False

    # ── MediaMTX ─────────────────────────────────────────────────────────────
    mediamtx_api_url: str = "http://mediamtx:9997"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── FCM ──────────────────────────────────────────────────────────────────
    fcm_server_key: str | None = None

    # ── Domain ───────────────────────────────────────────────────────────────
    domain_name: str = "localhost"
    host_ip: str = "127.0.0.1"

    @field_validator("database_url")
    @classmethod
    def ensure_asyncpg_scheme(cls, v: str) -> str:
        """Force asyncpg driver for async SQLAlchemy."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept comma-separated string or list from env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance. Cached after first call."""
    return Settings()


# Module-level singleton — import this everywhere
settings = get_settings()
