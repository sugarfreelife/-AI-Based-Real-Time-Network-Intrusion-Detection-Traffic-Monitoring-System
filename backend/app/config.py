"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    api_prefix: str = "/api/v1"

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(database_url=os.getenv("DATABASE_URL", "").strip() or "sqlite+pysqlite:///./nids.db")


settings = Settings.from_environment()
