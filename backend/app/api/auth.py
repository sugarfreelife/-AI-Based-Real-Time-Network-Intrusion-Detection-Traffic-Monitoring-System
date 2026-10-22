"""Login, refresh, logout, and administrator-only user management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database.models import AuditEventDB, RefreshSessionDB, UserDB
from backend.app.database.session import get_session
from backend.app.config import Settings
from backend.app.schemas import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserRead
from backend.app.security import (
    DUMMY_PASSWORD_HASH,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    AuthConfigurationError,
    decode_token,
    hash_jti,
    hash_password,
    issue_token_pair,
    validate_secret,
    verify_password,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


def _audit(
    session: Session,
    event_type: str,
    *,
    actor_user_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(AuditEventDB(
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    ))


def _settings(request: Request) -> Settings:
    return request.app.state.auth_config


def _issue_pair(session: Session, user: UserDB, settings: Settings) -> TokenPair:
    access, refresh, refresh_jti, refresh_expires = issue_token_pair(user_id=user.id, settings=settings)
    session.add(RefreshSessionDB(
        user_id=user.id,
        jti_hash=hash_jti(refresh_jti),
        expires_at=refresh_expires,
    ))
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UserDB:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_token(credentials.credentials, settings=_settings(request), expected_type=TOKEN_TYPE_ACCESS)
    except (jwt.PyJWTError, AuthConfigurationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    user = session.get(UserDB, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed: str):
    def dependency(
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[UserDB, Depends(get_current_user)],
    ) -> UserDB:
        if user.role not in allowed:
            _audit(
                session,
                "auth.authorization_denied",
                actor_user_id=user.id,
                target_type="route",
                target_id=request.url.path,
                details={"role": user.role, "method": request.method, "required_roles": list(allowed)},
            )
            session.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return user

    return dependency


@auth_router.post("/token", response_model=TokenPair)
def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> TokenPair:
    config = _settings(request)
    try:
        validate_secret(config)
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    username = payload.username.strip().lower()
    user = session.scalar(select(UserDB).where(UserDB.username == username))
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not user.is_active or not valid:
        _audit(session, "auth.login_failed", details={"username": username})
        session.commit()
        failed = True
        result = None
    else:
        now = datetime.now(UTC)
        user.last_login_at = now
        _audit(session, "auth.login_succeeded", actor_user_id=user.id, target_type="user", target_id=user.id)
        result = _issue_pair(session, user, config)
        session.commit()
        failed = False
    if failed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    assert result is not None
    return result


@auth_router.post("/refresh", response_model=TokenPair)
def refresh_token(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> TokenPair:
    """Rotate the refresh session and issue a new short-lived access token."""
    config = _settings(request)
    try:
        claims = decode_token(payload.refresh_token, settings=config, expected_type=TOKEN_TYPE_REFRESH)
        validate_secret(config)
    except (jwt.PyJWTError, AuthConfigurationError):
        raise HTTPException(status_code=401, detail="invalid or expired refresh token") from None
    refresh_session = session.scalar(
        select(RefreshSessionDB)
        .where(RefreshSessionDB.jti_hash == hash_jti(claims["jti"]))
        .with_for_update()
    )
    user = session.get(UserDB, claims["sub"])
    now = datetime.now(UTC)
    if refresh_session is None or user is None or not user.is_active:
        session.commit()
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    if refresh_session.revoked_at is not None:
        session.execute(
            update(RefreshSessionDB)
            .where(RefreshSessionDB.user_id == user.id, RefreshSessionDB.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        _audit(session, "auth.refresh_reuse_detected", actor_user_id=user.id, target_type="user", target_id=user.id)
        session.commit()
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    if refresh_session.expires_at <= now:
        refresh_session.revoked_at = now
        _audit(session, "auth.refresh_expired", actor_user_id=user.id, target_type="user", target_id=user.id)
        session.commit()
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")

    refresh_session.revoked_at = now
    result = _issue_pair(session, user, config)
    _audit(session, "auth.refresh_succeeded", actor_user_id=user.id, target_type="user", target_id=user.id)
    session.commit()
    return result


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    try:
        claims = decode_token(payload.refresh_token, settings=_settings(request), expected_type=TOKEN_TYPE_REFRESH)
    except (jwt.PyJWTError, AuthConfigurationError):
        raise HTTPException(status_code=401, detail="invalid or expired refresh token") from None
    refresh_session = session.scalar(
        select(RefreshSessionDB)
        .where(RefreshSessionDB.jti_hash == hash_jti(claims["jti"]))
        .with_for_update()
    )
    if refresh_session is None or refresh_session.user_id != claims["sub"]:
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    if refresh_session.revoked_at is None:
        refresh_session.revoked_at = datetime.now(UTC)
        _audit(
            session,
            "auth.logout",
            actor_user_id=refresh_session.user_id,
            target_type="user",
            target_id=refresh_session.user_id,
        )
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get("/me", response_model=UserRead)
def me(user: Annotated[UserDB, Depends(get_current_user)]) -> UserDB:
    return user


@auth_router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[UserDB, Depends(require_roles("admin"))],
) -> UserDB:
    user = UserDB(
        username=payload.username.strip().lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    try:
        session.add(user)
        session.flush()
        _audit(
            session,
            "user.created",
            actor_user_id=actor.id,
            target_type="user",
            target_id=user.id,
            details={"username": user.username, "role": user.role},
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="username already exists") from None
    return user
