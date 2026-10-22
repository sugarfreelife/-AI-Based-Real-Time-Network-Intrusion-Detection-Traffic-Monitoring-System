"""Persist a flow, its inference result, and all related alerts atomically."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy.orm import Session

from backend.app.database.models import AlertDB, FlowRecordDB, PredictionDB
from nids_engine.detection import Alert
from nids_engine.features import extract_features
from nids_engine.flows import FlowRecord
from nids_engine.inference import PredictionResult


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def persist_observation(
    session: Session,
    *,
    capture_id: str,
    flow: FlowRecord,
    prediction: PredictionResult,
    alerts: Sequence[Alert],
) -> FlowRecordDB:
    """Add one complete observation to the caller's current transaction."""

    if not capture_id.strip():
        raise ValueError("capture_id cannot be empty")
    flow_row = FlowRecordDB(
        capture_id=capture_id,
        flow_id=flow.flow_id,
        protocol=flow.protocol,
        endpoint_a={"ip": flow.endpoint_a.ip, "port": flow.endpoint_a.port},
        endpoint_b={"ip": flow.endpoint_b.ip, "port": flow.endpoint_b.port},
        started_at=flow.started_at,
        last_seen_at=flow.last_seen_at,
        ended_at=flow.ended_at,
        finalization_reason=flow.finalization_reason.value,
        features=extract_features(flow).as_dict(),
    )
    session.add(flow_row)
    session.flush()
    session.add(PredictionDB(
        flow_record_id=flow_row.id,
        status=prediction.status,
        predicted_label=prediction.predicted_label,
        model_version=prediction.model_version,
        feature_schema_version=prediction.feature_schema_version,
        predicted_at=_parse_timestamp(prediction.predicted_at_utc),
        reason=prediction.reason,
    ))
    for alert in alerts:
        session.add(AlertDB(
            id=alert.alert_id,
            flow_record_id=flow_row.id,
            detection_code=alert.detection_code,
            source=alert.source,
            severity=alert.severity,
            title=alert.title,
            explanation=alert.explanation,
            occurred_at=_parse_timestamp(alert.occurred_at_utc),
            protocol=alert.protocol,
            endpoint_a=alert.endpoint_a,
            endpoint_b=alert.endpoint_b,
            model_version=alert.model_version,
            evidence=alert.evidence,
            status=alert.status,
        ))
    session.flush()
    return flow_row
