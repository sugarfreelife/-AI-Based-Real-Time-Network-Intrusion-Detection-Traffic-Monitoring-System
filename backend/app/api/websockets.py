"""Authenticated polling stream for alerts persisted by any monitor process."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.database.models import AlertDB, UserDB
from backend.app.schemas import AlertRead
from backend.app.security import TOKEN_TYPE_ACCESS, AuthConfigurationError, decode_token

logger = logging.getLogger("backend.websocket")
websocket_router = APIRouter()
AUTH_TIMEOUT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.5
MAX_ALERT_BATCH = 100


def _parse_cursor(payload: dict[str, Any], default_time: datetime) -> tuple[datetime, str]:
    raw_time = payload.get("after_created_at")
    raw_id = payload.get("after_id")
    if raw_time is None and raw_id is None:
        return default_time, ""
    if not isinstance(raw_time, str) or not isinstance(raw_id, str) or len(raw_id) > 64:
        raise ValueError("both after_created_at and after_id are required")
    parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("after_created_at must include a timezone")
    return parsed.astimezone(UTC), raw_id


@websocket_router.websocket("/api/v1/ws/alerts")
async def alert_stream(websocket: WebSocket) -> None:
    started_at = datetime.now(UTC)
    await websocket.accept()
    try:
        handshake = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="authentication required")
        return
    except WebSocketDisconnect:
        return
    except ValueError:
        await websocket.close(code=4401, reason="authentication required")
        return
    if not isinstance(handshake, dict) or not isinstance(handshake.get("access_token"), str):
        await websocket.close(code=4401, reason="authentication required")
        return

    app = websocket.app
    settings = app.state.auth_config
    session_factory = app.state.session_factory
    user_id = ""
    try:
        claims = decode_token(handshake["access_token"], settings=settings, expected_type=TOKEN_TYPE_ACCESS)
        cursor_time, cursor_id = _parse_cursor(handshake, started_at)
        with session_factory() as session:
            user = session.get(UserDB, claims["sub"])
            if user is None or not user.is_active:
                raise ValueError("inactive user")
            user_id = user.id
    except (jwt.PyJWTError, AuthConfigurationError, ValueError, TypeError):
        await websocket.close(code=4401, reason="invalid access token")
        return

    await websocket.send_json({"type": "ready", "user_id": user_id})
    try:
        while True:
            if datetime.fromtimestamp(claims["exp"], UTC) <= datetime.now(UTC):
                await websocket.close(code=4401, reason="access token expired")
                return
            with session_factory() as session:
                rows = session.scalars(
                    select(AlertDB)
                    .where(
                        or_(
                            AlertDB.created_at > cursor_time,
                            (AlertDB.created_at == cursor_time) & (AlertDB.id > cursor_id),
                        )
                    )
                    .order_by(AlertDB.created_at, AlertDB.id)
                    .limit(MAX_ALERT_BATCH)
                ).all()
                items = [AlertRead.model_validate(row).model_dump(mode="json") for row in rows]
            for item in items:
                await websocket.send_json({"type": "alert", "data": item})
                cursor_time = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                cursor_id = item["id"]
            if not items:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
    except SQLAlchemyError:
        logger.exception("alert_stream_database_error")
        try:
            await websocket.close(code=1011, reason="alert storage unavailable")
        except RuntimeError:
            pass
