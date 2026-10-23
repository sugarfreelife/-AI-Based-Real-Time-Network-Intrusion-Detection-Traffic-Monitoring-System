"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bounded_int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    api_prefix: str = "/api/v1"
    jwt_secret_key: str = ""
    jwt_issuer: str = "nids-api"
    jwt_audience: str = "nids-client"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    model_path: str | None = None
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    login_rate_limit_block_seconds: int = 300
    login_rate_limit_max_entries: int = 10_000

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            database_url=os.getenv("DATABASE_URL", "").strip() or "sqlite+pysqlite:///./nids.db",
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", "").strip(),
            jwt_issuer=os.getenv("JWT_ISSUER", "nids-api").strip() or "nids-api",
            jwt_audience=os.getenv("JWT_AUDIENCE", "nids-client").strip() or "nids-client",
            cors_origins=tuple(
                origin.strip().rstrip("/")
                for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
                if origin.strip()
            ),
            model_path=os.getenv("MODEL_PATH", "").strip() or None,
            login_rate_limit_attempts=_bounded_int_env(
                "LOGIN_RATE_LIMIT_ATTEMPTS", 5, minimum=1, maximum=100
            ),
            login_rate_limit_window_seconds=_bounded_int_env(
                "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300, minimum=1, maximum=86_400
            ),
            login_rate_limit_block_seconds=_bounded_int_env(
                "LOGIN_RATE_LIMIT_BLOCK_SECONDS", 300, minimum=1, maximum=86_400
            ),
            login_rate_limit_max_entries=_bounded_int_env(
                "LOGIN_RATE_LIMIT_MAX_ENTRIES", 10_000, minimum=2, maximum=100_000
            ),
        )


settings = Settings.from_environment()
