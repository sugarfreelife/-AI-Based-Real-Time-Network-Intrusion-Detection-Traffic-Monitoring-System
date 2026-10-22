"""SQLAlchemy engine and request-scoped sessions."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import settings


def make_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if database_url in {"sqlite://", "sqlite+pysqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
            engine_options["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, **engine_options)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
