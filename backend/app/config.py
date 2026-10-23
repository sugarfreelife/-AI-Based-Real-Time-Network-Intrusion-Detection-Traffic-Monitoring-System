"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
        )


settings = Settings.from_environment()
