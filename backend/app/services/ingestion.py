"""Persist a flow, its inference result, and all related alerts atomically."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.database.models import AlertDB, FlowRecordDB, PredictionDB
from nids_engine.detection import Alert
from nids_engine.features import extract_features
from nids_engine.flows import FlowRecord
from nids_engine.inference import PredictionResult


class IngestionConflict(ValueError):
    """A stable capture identity was reused for different data."""

    failure_code = "capture_identity_conflict"


@dataclass(frozen=True, slots=True)
class PersistedObservation:
    record: FlowRecordDB
    created: bool


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _flow_values(capture_id: str, flow: FlowRecord) -> dict[str, object]:
    return {
        "capture_id": capture_id,
        "flow_id": flow.flow_id,
        "protocol": flow.protocol,
        "endpoint_a": {"ip": flow.endpoint_a.ip, "port": flow.endpoint_a.port},
        "endpoint_b": {"ip": flow.endpoint_b.ip, "port": flow.endpoint_b.port},
        "started_at": _utc(flow.started_at),
        "last_seen_at": _utc(flow.last_seen_at),
        "ended_at": _utc(flow.ended_at),
        "finalization_reason": flow.finalization_reason.value,
        "features": extract_features(flow).as_dict(),
    }


def _prediction_values(prediction: PredictionResult) -> dict[str, object]:
    # predicted_at is intentionally omitted: a replay retry creates a new inference
    # timestamp even when it produces the same stable prediction.
    return {
        "status": prediction.status,
        "predicted_label": prediction.predicted_label,
        "model_version": prediction.model_version,
        "feature_schema_version": prediction.feature_schema_version,
        "reason": prediction.reason,
    }


def _alert_values(alert: Alert) -> dict[str, object]:
    # Alert IDs are generated per process. Workflow state is also omitted so a
    # replay cannot reset an alert an analyst has already acknowledged.
    return {
        "detection_code": alert.detection_code,
        "source": alert.source,
        "severity": alert.severity,
        "title": alert.title,
        "explanation": alert.explanation,
        "occurred_at": _parse_timestamp(alert.occurred_at_utc),
        "protocol": alert.protocol,
        "endpoint_a": alert.endpoint_a,
        "endpoint_b": alert.endpoint_b,
        "model_version": alert.model_version,
        "evidence": alert.evidence,
    }


def _alert_row_values(alert: AlertDB) -> dict[str, object]:
    return {
        "detection_code": alert.detection_code,
        "source": alert.source,
        "severity": alert.severity,
        "title": alert.title,
        "explanation": alert.explanation,
        "occurred_at": _utc(alert.occurred_at),
        "protocol": alert.protocol,
        "endpoint_a": alert.endpoint_a,
        "endpoint_b": alert.endpoint_b,
        "model_version": alert.model_version,
        "evidence": alert.evidence,
    }


def _canonical_alerts(alerts: Sequence[dict[str, object]]) -> list[str]:
    return sorted(json.dumps(alert, sort_keys=True, separators=(",", ":"), default=str) for alert in alerts)


def _load_observation(session: Session, capture_id: str, flow_id: str) -> FlowRecordDB | None:
    return session.scalar(
        select(FlowRecordDB)
        .where(FlowRecordDB.capture_id == capture_id, FlowRecordDB.flow_id == flow_id)
        .options(selectinload(FlowRecordDB.prediction), selectinload(FlowRecordDB.alerts))
    )


def _ensure_same_observation(
    row: FlowRecordDB,
    *,
    flow_values: dict[str, object],
    prediction: PredictionResult,
    alerts: Sequence[Alert],
) -> None:
    persisted_flow = {
        name: getattr(row, name)
        for name in flow_values
        if name not in {"capture_id", "flow_id"}
    }
    expected_flow = {
        name: value
        for name, value in flow_values.items()
        if name not in {"capture_id", "flow_id"}
    }
    for name in ("started_at", "last_seen_at", "ended_at"):
        persisted_flow[name] = _utc(persisted_flow[name])  # type: ignore[arg-type]
    if persisted_flow != expected_flow:
        raise IngestionConflict(
            f"capture ID {row.capture_id!r} has different flow data for {row.flow_id!r}"
        )

    if row.prediction is None or any(
        getattr(row.prediction, name) != value
        for name, value in _prediction_values(prediction).items()
    ):
        raise IngestionConflict(
            f"capture ID {row.capture_id!r} has a different prediction for {row.flow_id!r}"
        )

    existing_alerts = _canonical_alerts([_alert_row_values(alert) for alert in row.alerts])
    requested_alerts = _canonical_alerts([_alert_values(alert) for alert in alerts])
    if existing_alerts != requested_alerts:
        raise IngestionConflict(
            f"capture ID {row.capture_id!r} has different alerts for {row.flow_id!r}"
        )


def persist_observation(
    session: Session,
    *,
    capture_id: str,
    flow: FlowRecord,
    prediction: PredictionResult,
    alerts: Sequence[Alert],
) -> PersistedObservation:
    """Insert a complete observation once per capture and flow identity.

    Matching retries return the stored record unchanged, including alert
    acknowledgement state. Reusing the identity for different payload or
    inference results raises :class:`IngestionConflict`.
    """

    if not capture_id.strip():
        raise ValueError("capture_id cannot be empty")
    flow_values = _flow_values(capture_id, flow)
    existing = _load_observation(session, capture_id, flow.flow_id)
    if existing is not None:
        _ensure_same_observation(existing, flow_values=flow_values, prediction=prediction, alerts=alerts)
        return PersistedObservation(existing, created=False)

    try:
        # The savepoint allows a concurrent retry to win the unique-key race
        # without invalidating the caller's outer transaction.
        with session.begin_nested():
            flow_row = FlowRecordDB(**flow_values)
            session.add(flow_row)
            session.flush()
            session.add(PredictionDB(
                flow_record_id=flow_row.id,
                **_prediction_values(prediction),
                predicted_at=_parse_timestamp(prediction.predicted_at_utc),
            ))
            for alert in alerts:
                session.add(AlertDB(
                    id=alert.alert_id,
                    flow_record_id=flow_row.id,
                    **_alert_values(alert),
                    status=alert.status,
                ))
            session.flush()
    except IntegrityError:
        existing = _load_observation(session, capture_id, flow.flow_id)
        if existing is None:
            raise
        _ensure_same_observation(existing, flow_values=flow_values, prediction=prediction, alerts=alerts)
        return PersistedObservation(existing, created=False)

    return PersistedObservation(flow_row, created=True)
