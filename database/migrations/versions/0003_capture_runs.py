"""Persist monitor execution summaries."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_capture_runs"
down_revision: str | None = "0002_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_runs",
        sa.Column("capture_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("packets_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("packets_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("packets_filtered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsing_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flow_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unscored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_duplicate_alerts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_status", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("elapsed_seconds", sa.Float(), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_capture_runs_started_at", "capture_runs", ["started_at"])
    op.create_index("ix_capture_runs_status_started", "capture_runs", ["status", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_capture_runs_status_started", table_name="capture_runs")
    op.drop_index("ix_capture_runs_started_at", table_name="capture_runs")
    op.drop_table("capture_runs")
