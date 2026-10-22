"""Password and signed-token helpers used by the API authentication layer."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.config import Settings

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
PASSWORD_HASHER = PasswordHash.recommended()
# Verify unknown-user passwords with Argon2 as well, reducing username timing leaks.
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("not-a-valid-user-password")


class AuthConfigurationError(ValueError):
    """Raised when JWT signing is requested without a valid secret."""


def validate_secret(settings: Settings) -> bytes:
    secret = settings.jwt_secret_key.encode("utf-8")
    if len(secret) < 32:
        raise AuthConfigurationError("JWT_SECRET_KEY must contain at least 32 UTF-8 bytes")
    return secret


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password, encoded_hash)
    except Exception:
        return False


def hash_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def issue_token(
    *,
    user_id: str,
    settings: Settings,
    token_type: str,
    expires_at: datetime,
    now: datetime | None = None,
) -> tuple[str, str]:
    issued_at = now or datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user_id,
        "jti": jti,
        "typ": token_type,
        "iat": int(issued_at.timestamp()),
        "nbf": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded = jwt.encode(payload, validate_secret(settings), algorithm=ALGORITHM)
    return encoded, jti


def issue_token_pair(
    *, user_id: str, settings: Settings, now: datetime | None = None
) -> tuple[str, str, str, datetime]:
    issued_at = now or datetime.now(UTC)
    access_expires = issued_at + timedelta(minutes=settings.access_token_minutes)
    refresh_expires = issued_at + timedelta(days=settings.refresh_token_days)
    access_token, _ = issue_token(
        user_id=user_id,
        settings=settings,
        token_type=TOKEN_TYPE_ACCESS,
        expires_at=access_expires,
        now=issued_at,
    )
    refresh_token, refresh_jti = issue_token(
        user_id=user_id,
        settings=settings,
        token_type=TOKEN_TYPE_REFRESH,
        expires_at=refresh_expires,
        now=issued_at,
    )
    return access_token, refresh_token, refresh_jti, refresh_expires


def decode_token(token: str, *, settings: Settings, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        validate_secret(settings),
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "jti", "typ"]},
        leeway=5,
    )
    if payload.get("typ") != expected_type:
        raise InvalidTokenError("unexpected token type")
    return payload
