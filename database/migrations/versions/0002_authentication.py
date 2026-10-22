"""Add users, rotating refresh sessions, audit trail, and alert acknowledgements."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_authentication"
down_revision: str | None = "0001_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_role_active", "users", ["role", "is_active"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_refresh_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("jti_hash", name="uq_refresh_sessions_jti_hash"),
    )
    op.create_index("ix_refresh_sessions_user_expiry", "refresh_sessions", ["user_id", "expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_audit_events_actor_user_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_actor_time", "audit_events", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_events_type_time", "audit_events", ["event_type", "occurred_at"])

    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("alerts", recreate="always") as batch:
            batch.add_column(sa.Column("acknowledged_by_user_id", sa.String(length=36), nullable=True))
            batch.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
            batch.create_foreign_key(
                "fk_alerts_acknowledged_by_user_id_users",
                "users",
                ["acknowledged_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.add_column("alerts", sa.Column("acknowledged_by_user_id", sa.String(length=36), nullable=True))
        op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
        op.create_foreign_key(
            "fk_alerts_acknowledged_by_user_id_users",
            "alerts",
            "users",
            ["acknowledged_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("alerts", recreate="always") as batch:
            batch.drop_constraint("fk_alerts_acknowledged_by_user_id_users", type_="foreignkey")
            batch.drop_column("acknowledged_at")
            batch.drop_column("acknowledged_by_user_id")
    else:
        op.drop_constraint("fk_alerts_acknowledged_by_user_id_users", "alerts", type_="foreignkey")
        op.drop_column("alerts", "acknowledged_at")
        op.drop_column("alerts", "acknowledged_by_user_id")
    op.drop_index("ix_audit_events_type_time", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_time", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_refresh_sessions_user_expiry", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_index("ix_users_role_active", table_name="users")
    op.drop_table("users")
