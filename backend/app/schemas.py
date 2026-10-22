"""Validated API response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime


ItemType = TypeVar("ItemType")


class Page(BaseModel, Generic[ItemType]):
    items: list[ItemType]
    total: int
    limit: int
    offset: int
