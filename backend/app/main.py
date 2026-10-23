"""FastAPI app factory and health endpoints."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.auth import auth_router
from backend.app.api.routes import router
from backend.app.api.websockets import websocket_router
from backend.app.config import Settings, settings
from backend.app.database.session import SessionLocal, get_session
from backend.app.rate_limit import LoginRateLimiter
from backend.app.services.model_status import ModelStatusProvider

logger = logging.getLogger("backend.health")


def create_app(
    session_factory: sessionmaker[Session] = SessionLocal,
    auth_config: Settings = settings,
) -> FastAPI:
    app = FastAPI(
        title="NIDS API",
        version="0.1.0",
        description="Read persisted flow, prediction, and alert records from the NIDS pipeline.",
    )

    def request_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = request_session
    app.state.session_factory = session_factory
    app.state.auth_config = auth_config
    app.state.model_status = ModelStatusProvider(auth_config.model_path)
    app.state.login_rate_limiter = LoginRateLimiter(
        attempts=auth_config.login_rate_limit_attempts,
        window_seconds=auth_config.login_rate_limit_window_seconds,
        block_seconds=auth_config.login_rate_limit_block_seconds,
        max_entries=auth_config.login_rate_limit_max_entries,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(auth_config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

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
    app.include_router(auth_router)
    app.include_router(websocket_router)
    return app


app = create_app()
