"""Validated API response shapes."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EndpointRead(BaseModel):
    ip: str | None = None
    port: int | None = Field(default=None, ge=0, le=65535)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    predicted_label: str | None
    model_version: str | None
    feature_schema_version: str
    predicted_at: datetime
    reason: str | None


class FlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    capture_id: str
    flow_id: str
    protocol: str
    endpoint_a: EndpointRead
    endpoint_b: EndpointRead
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime
    finalization_reason: str
    features: dict[str, float]
    prediction: PredictionRead | None = None
    created_at: datetime


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flow_record_id: str
    detection_code: str
    source: str
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    explanation: str
    occurred_at: datetime
    protocol: str
    endpoint_a: EndpointRead
    endpoint_b: EndpointRead
    model_version: str | None
    evidence: dict[str, Any]
    status: Literal["new", "acknowledged"]
    acknowledged_by_user_id: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime


class CaptureRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capture_id: str
    source_name: str
    status: Literal["running", "completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime | None
    attempt_count: int = Field(ge=1)
    packets_seen: int = Field(ge=0)
    packets_processed: int = Field(ge=0)
    packets_filtered: int = Field(ge=0)
    parsing_failures: int = Field(ge=0)
    read_failures: int = Field(ge=0)
    flow_count: int = Field(ge=0)
    duplicate_flows: int = Field(ge=0)
    scored_count: int = Field(ge=0)
    unscored_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    suppressed_duplicate_alerts: int = Field(ge=0)
    model_status: str
    model_version: str | None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    failure_reason: str | None


class AnalyticsSummaryRead(BaseModel):
    since: datetime
    until: datetime
    flow_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    capture_run_count: int = Field(ge=0)
    capture_runs_by_status: dict[str, int]
    alerts_by_severity: dict[str, int]
    flows_by_protocol: dict[str, int]


class AnalyticsBucketRead(BaseModel):
    timestamp: datetime
    flow_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)


class AnalyticsTimelineRead(BaseModel):
    since: datetime
    until: datetime
    bucket: Literal["hour", "day"]
    items: list[AnalyticsBucketRead]


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=8192)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=1)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "analyst", "viewer"]

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", normalized) is None:
            raise ValueError("username must use 3-64 letters, digits, dots, underscores, or hyphens")
        return normalized


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: Literal["admin", "analyst", "viewer"]
    is_active: bool
    created_at: datetime


ItemType = TypeVar("ItemType")


class Page(BaseModel, Generic[ItemType]):
    items: list[ItemType]
    total: int
    limit: int
    offset: int
