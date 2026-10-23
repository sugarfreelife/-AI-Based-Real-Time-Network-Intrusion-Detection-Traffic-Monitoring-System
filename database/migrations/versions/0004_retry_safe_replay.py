"""Track capture retry attempts and duplicate flows."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_retry_safe_replay"
down_revision: str | None = "0003_capture_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "capture_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "capture_runs",
        sa.Column("duplicate_flows", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("capture_runs", "duplicate_flows")
    op.drop_column("capture_runs", "attempt_count")
