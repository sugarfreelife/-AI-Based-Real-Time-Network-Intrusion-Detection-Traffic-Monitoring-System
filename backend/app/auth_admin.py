"""Provision the first administrator without exposing public registration."""

from __future__ import annotations

import argparse
from getpass import getpass

from sqlalchemy import select

from backend.app.database.models import AuditEventDB, UserDB
from backend.app.database.session import SessionLocal
from backend.app.schemas import UserCreate
from backend.app.security import hash_password, validate_secret
from backend.app.config import settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the initial NIDS administrator account.")
    parser.add_argument("--username", help="administrator username; prompts when omitted")
    args = parser.parse_args(argv)
    try:
        validate_secret(settings)
    except ValueError as exc:
        parser.error(str(exc))
    username = (args.username or input("Administrator username: ")).strip().lower()
    password = getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass("Repeat password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    try:
        payload = UserCreate(username=username, password=password, role="admin")
    except Exception as exc:
        parser.error(str(exc))

    with SessionLocal() as session:
        if session.scalar(select(UserDB.id).where(UserDB.role == "admin")) is not None:
            parser.error("an administrator already exists; use the admin-only API to add users")
        user = UserDB(
            username=payload.username,
            password_hash=hash_password(password),
            role="admin",
        )
        session.add(user)
        session.flush()
        session.add(AuditEventDB(
            actor_user_id=user.id,
            event_type="user.bootstrap_admin",
            target_type="user",
            target_id=user.id,
            details={"username": user.username, "role": "admin"},
        ))
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(f"Created administrator account '{username}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
