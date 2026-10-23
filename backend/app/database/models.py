"""SQLAlchemy records for persisted flows, predictions, and alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
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


class CaptureRunDB(Base):
    """Operational summary for one offline replay or explicitly started capture."""

    __tablename__ = "capture_runs"
    __table_args__ = (
        Index("ix_capture_runs_started_at", "started_at"),
        Index("ix_capture_runs_status_started", "status", "started_at"),
    )

    capture_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    packets_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    packets_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    packets_filtered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parsing_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    read_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flow_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_flows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    scored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unscored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    suppressed_duplicate_alerts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_status: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128))
    elapsed_seconds: Mapped[float | None] = mapped_column(Float)
    failure_reason: Mapped[str | None] = mapped_column(String(64))


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
    acknowledged_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(
            "users.id", ondelete="SET NULL", name="fk_alerts_acknowledged_by_user_id_users"
        )
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)

    flow: Mapped[FlowRecordDB] = relationship(back_populates="alerts")


class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_role_active", "role", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, onupdate=_now_utc, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class RefreshSessionDB(Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        UniqueConstraint("jti_hash", name="uq_refresh_sessions_jti_hash"),
        Index("ix_refresh_sessions_user_expiry", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey(
        "users.id", ondelete="CASCADE", name="fk_refresh_sessions_user_id_users"
    ), nullable=False)
    jti_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AuditEventDB(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_actor_time", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_type_time", "event_type", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(
        "users.id", ondelete="SET NULL", name="fk_audit_events_actor_user_id_users"
    ))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now_utc, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
