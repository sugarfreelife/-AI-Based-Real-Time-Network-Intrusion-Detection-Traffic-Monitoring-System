"""Create flow, prediction, and alert persistence tables."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flows",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("flow_id", sa.String(length=64), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("endpoint_a", sa.JSON(), nullable=False),
        sa.Column("endpoint_b", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalization_reason", sa.String(length=32), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("capture_id", "flow_id", name="uq_flows_capture_flow"),
    )
    op.create_index("ix_flows_ended_at", "flows", ["ended_at"])
    op.create_index("ix_flows_protocol_ended", "flows", ["protocol", "ended_at"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("flow_record_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("predicted_label", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("feature_schema_version", sa.String(length=32), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["flow_record_id"], ["flows.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("flow_record_id", name="uq_predictions_flow_record"),
    )
    op.create_index("ix_predictions_status", "predictions", ["status"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("flow_record_id", sa.String(length=36), nullable=False),
        sa.Column("detection_code", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("explanation", sa.String(length=2048), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("endpoint_a", sa.JSON(), nullable=False),
        sa.Column("endpoint_b", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["flow_record_id"], ["flows.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_severity_occurred", "alerts", ["severity", "occurred_at"])
    op.create_index("ix_alerts_status_occurred", "alerts", ["status", "occurred_at"])
    op.create_index("ix_alerts_detection_code", "alerts", ["detection_code"])


def downgrade() -> None:
    op.drop_index("ix_alerts_detection_code", table_name="alerts")
    op.drop_index("ix_alerts_status_occurred", table_name="alerts")
    op.drop_index("ix_alerts_severity_occurred", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_predictions_status", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index("ix_flows_protocol_ended", table_name="flows")
    op.drop_index("ix_flows_ended_at", table_name="flows")
    op.drop_table("flows")
