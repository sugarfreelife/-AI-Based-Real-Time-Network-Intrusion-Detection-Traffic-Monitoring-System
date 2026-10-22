"""FastAPI app factory and health endpoints."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.routes import router
from backend.app.database.session import SessionLocal, get_session

logger = logging.getLogger("backend.health")


def create_app(session_factory: sessionmaker[Session] = SessionLocal) -> FastAPI:
    app = FastAPI(
        title="NIDS API",
        version="0.1.0",
        description="Read persisted flow, prediction, and alert records from the NIDS pipeline.",
    )

    def request_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = request_session

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: Session = Depends(request_session)) -> Any:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("database_readiness_failed")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "degraded", "database": "unavailable"},
            )
        return {"status": "ready", "database": "available"}

    app.include_router(router)
    return app


app = create_app()
