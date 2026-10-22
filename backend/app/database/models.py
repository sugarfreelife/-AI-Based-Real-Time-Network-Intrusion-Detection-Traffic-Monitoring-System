"""SQLAlchemy records for persisted flows, predictions, and alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, UTCDateTime


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(UTC)


class FlowRecordDB(Base):
    __tablename__ = "flows"
    __table_args__ = (
        UniqueConstraint("capture_id", "flow_id", name="uq_flows_capture_flow"),
        Index("ix_flows_ended_at", "ended_at"),
        Index("ix_flows_protocol_ended", "protocol", "ended_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    capture_id: Mapped[str] = mapped_column(String(36), nullable=False)
    flow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint_a: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    endpoint_b: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finalization_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    features: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)

    prediction: Mapped[PredictionDB | None] = relationship(
        back_populates="flow", uselist=False, cascade="all, delete-orphan"
    )
    alerts: Mapped[list[AlertDB]] = relationship(back_populates="flow", cascade="all, delete-orphan")


class PredictionDB(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("flow_record_id", name="uq_predictions_flow_record"),
        Index("ix_predictions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    flow_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    predicted_label: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(128))
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128))

    flow: Mapped[FlowRecordDB] = relationship(back_populates="prediction")


class AlertDB(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_severity_occurred", "severity", "occurred_at"),
        Index("ix_alerts_status_occurred", "status", "occurred_at"),
        Index("ix_alerts_detection_code", "detection_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    flow_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    detection_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    explanation: Mapped[str] = mapped_column(String(2048), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint_a: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    endpoint_b: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)

    flow: Mapped[FlowRecordDB] = relationship(back_populates="alerts")
