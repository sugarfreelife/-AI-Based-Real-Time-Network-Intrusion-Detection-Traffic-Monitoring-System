"""Validated, authenticated REST resources for persisted flow observations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.auth import _audit, get_current_user, require_roles
from backend.app.database.models import AlertDB, CaptureRunDB, FlowRecordDB, UserDB
from backend.app.database.session import get_session
from backend.app.schemas import (
    AlertRead,
    AnalyticsBucketRead,
    AnalyticsSummaryRead,
    AnalyticsTimelineRead,
    CaptureRunRead,
    FlowRead,
    ModelStatusRead,
    Page,
)

router = APIRouter(prefix="/api/v1")

CaptureStatus = Literal["running", "completed", "partial", "failed"]


@router.get("/model/status", response_model=ModelStatusRead)
def get_model_status(
    request: Request,
    _user: Annotated[UserDB, Depends(get_current_user)],
) -> ModelStatusRead:
    """Return verified metadata for the operator-configured model and report."""

    return ModelStatusRead.model_validate(request.app.state.model_status.get())


def _validate_range(since: datetime | None, until: datetime | None) -> None:
    for name, value in (("since", since), ("until", until)):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(status_code=422, detail=f"{name} must include a timezone")
    if since is not None and until is not None and since > until:
        raise HTTPException(status_code=422, detail="since must be earlier than or equal to until")


@router.get("/captures", response_model=Page[CaptureRunRead])
def list_capture_runs(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    capture_status: Annotated[CaptureStatus | None, Query(alias="status")] = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Page[CaptureRunRead]:
    """List persisted capture attempts, filtering time ranges by start time."""

    _validate_range(since, until)
    statement = select(CaptureRunDB)
    count_statement = select(func.count()).select_from(CaptureRunDB)
    conditions = []
    if capture_status is not None:
        conditions.append(CaptureRunDB.status == capture_status)
    if since is not None:
        conditions.append(CaptureRunDB.started_at >= since)
    if until is not None:
        conditions.append(CaptureRunDB.started_at <= until)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = int(session.scalar(count_statement) or 0)
    records = session.scalars(
        statement.order_by(CaptureRunDB.started_at.desc(), CaptureRunDB.capture_id)
        .offset(offset)
        .limit(limit)
    ).all()
    return Page[CaptureRunRead](items=records, total=total, limit=limit, offset=offset)


@router.get("/captures/{capture_id}", response_model=CaptureRunRead)
def get_capture_run(
    capture_id: str,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
) -> CaptureRunRead:
    record = session.get(CaptureRunDB, capture_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capture not found")
    return CaptureRunRead.model_validate(record)


def _analytics_range(since: datetime | None, until: datetime | None) -> tuple[datetime, datetime]:
    _validate_range(since, until)
    range_end = (until or datetime.now(UTC)).astimezone(UTC)
    range_start = (since or range_end - timedelta(hours=24)).astimezone(UTC)
    if range_start > range_end:
        raise HTTPException(status_code=422, detail="since must be earlier than or equal to until")
    return range_start, range_end


def _group_counts(session: Session, statement: Any) -> dict[str, int]:
    return {str(key): int(count) for key, count in session.execute(statement).all()}


@router.get("/analytics/summary", response_model=AnalyticsSummaryRead)
def analytics_summary(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
    since: datetime | None = None,
    until: datetime | None = None,
) -> AnalyticsSummaryRead:
    """Return persisted aggregate counts for the selected UTC event-time range."""

    range_start, range_end = _analytics_range(since, until)
    flow_range = (FlowRecordDB.ended_at >= range_start, FlowRecordDB.ended_at <= range_end)
    alert_range = (AlertDB.occurred_at >= range_start, AlertDB.occurred_at <= range_end)
    capture_range = (CaptureRunDB.started_at >= range_start, CaptureRunDB.started_at <= range_end)
    flow_count = int(session.scalar(select(func.count()).select_from(FlowRecordDB).where(*flow_range)) or 0)
    alert_count = int(session.scalar(select(func.count()).select_from(AlertDB).where(*alert_range)) or 0)
    capture_run_count = int(session.scalar(select(func.count()).select_from(CaptureRunDB).where(*capture_range)) or 0)
    capture_statuses = _group_counts(
        session,
        select(CaptureRunDB.status, func.count()).where(*capture_range).group_by(CaptureRunDB.status),
    )
    alert_severities = _group_counts(
        session,
        select(AlertDB.severity, func.count()).where(*alert_range).group_by(AlertDB.severity),
    )
    protocols = _group_counts(
        session,
        select(FlowRecordDB.protocol, func.count()).where(*flow_range).group_by(FlowRecordDB.protocol),
    )
    return AnalyticsSummaryRead(
        since=range_start,
        until=range_end,
        flow_count=flow_count,
        alert_count=alert_count,
        capture_run_count=capture_run_count,
        capture_runs_by_status={
            key: capture_statuses.get(key, 0) for key in ("running", "completed", "partial", "failed")
        },
        alerts_by_severity={
            key: alert_severities.get(key, 0) for key in ("low", "medium", "high", "critical")
        },
        flows_by_protocol=protocols,
    )


def _bucket_expression(session: Session, column: Any, bucket: str) -> Any:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return func.date_trunc(bucket, column, literal("UTC"))
    if dialect == "sqlite":
        timestamp_format = "%Y-%m-%dT%H:00:00Z" if bucket == "hour" else "%Y-%m-%dT00:00:00Z"
        return func.strftime(timestamp_format, column)
    raise HTTPException(status_code=503, detail="analytics bucket queries require PostgreSQL or SQLite")


def _bucket_datetime(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@router.get("/analytics/timeline", response_model=AnalyticsTimelineRead)
def analytics_timeline(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
    since: datetime | None = None,
    until: datetime | None = None,
    bucket: Literal["hour", "day"] = "hour",
) -> AnalyticsTimelineRead:
    """Return UTC time buckets for persisted flows and alerts, including empty buckets."""

    range_start, range_end = _analytics_range(since, until)
    max_range = timedelta(days=31 if bucket == "hour" else 366)
    if range_end - range_start > max_range:
        raise HTTPException(status_code=422, detail=f"{bucket} timeline range exceeds {max_range.days} days")

    step = timedelta(hours=1) if bucket == "hour" else timedelta(days=1)
    if bucket == "hour":
        bucket_start = range_start.replace(minute=0, second=0, microsecond=0)
        bucket_end = range_end.replace(minute=0, second=0, microsecond=0)
    else:
        bucket_start = range_start.replace(hour=0, minute=0, second=0, microsecond=0)
        bucket_end = range_end.replace(hour=0, minute=0, second=0, microsecond=0)
    flow_bucket = _bucket_expression(session, FlowRecordDB.ended_at, bucket)
    alert_bucket = _bucket_expression(session, AlertDB.occurred_at, bucket)
    flow_rows = session.execute(
        select(flow_bucket.label("bucket_at"), func.count())
        .where(FlowRecordDB.ended_at >= range_start, FlowRecordDB.ended_at <= range_end)
        .group_by(flow_bucket)
    ).all()
    alert_rows = session.execute(
        select(alert_bucket.label("bucket_at"), func.count())
        .where(AlertDB.occurred_at >= range_start, AlertDB.occurred_at <= range_end)
        .group_by(alert_bucket)
    ).all()
    flow_counts = {
        _bucket_datetime(timestamp): int(count) for timestamp, count in flow_rows if timestamp is not None
    }
    alert_counts = {
        _bucket_datetime(timestamp): int(count) for timestamp, count in alert_rows if timestamp is not None
    }

    items: list[AnalyticsBucketRead] = []
    current = bucket_start
    while current <= bucket_end:
        items.append(AnalyticsBucketRead(
            timestamp=current,
            flow_count=flow_counts.get(current, 0),
            alert_count=alert_counts.get(current, 0),
        ))
        current += step
    return AnalyticsTimelineRead(since=range_start, until=range_end, bucket=bucket, items=items)


@router.get("/flows", response_model=Page[FlowRead])
def list_flows(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    protocol: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Page[FlowRead]:
    _validate_range(since, until)
    statement = select(FlowRecordDB).options(selectinload(FlowRecordDB.prediction))
    count_statement = select(func.count()).select_from(FlowRecordDB)
    conditions = []
    if protocol:
        normalized = protocol.strip().upper()
        if normalized not in {"TCP", "UDP", "ICMP", "ICMPV6", "OTHER"}:
            raise HTTPException(status_code=422, detail="protocol must be TCP, UDP, ICMP, ICMPV6, or OTHER")
        conditions.append(FlowRecordDB.protocol == normalized)
    if since is not None:
        conditions.append(FlowRecordDB.ended_at >= since)
    if until is not None:
        conditions.append(FlowRecordDB.ended_at <= until)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = int(session.scalar(count_statement) or 0)
    records = session.scalars(
        statement.order_by(FlowRecordDB.ended_at.desc(), FlowRecordDB.id).offset(offset).limit(limit)
    ).all()
    return Page[FlowRead](items=records, total=total, limit=limit, offset=offset)


@router.get("/flows/{flow_record_id}", response_model=FlowRead)
def get_flow(
    flow_record_id: str,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
) -> FlowRead:
    record = session.scalar(
        select(FlowRecordDB)
        .options(selectinload(FlowRecordDB.prediction))
        .where(FlowRecordDB.id == flow_record_id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flow not found")
    return FlowRead.model_validate(record)


@router.get("/alerts", response_model=Page[AlertRead])
def list_alerts(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    severity: Literal["low", "medium", "high", "critical"] | None = None,
    alert_status: Annotated[Literal["new", "acknowledged"] | None, Query(alias="status")] = None,
    detection_code: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Page[AlertRead]:
    _validate_range(since, until)
    statement = select(AlertDB)
    count_statement = select(func.count()).select_from(AlertDB)
    conditions = []
    if severity is not None:
        conditions.append(AlertDB.severity == severity)
    if alert_status is not None:
        conditions.append(AlertDB.status == alert_status)
    if detection_code is not None:
        conditions.append(AlertDB.detection_code == detection_code)
    if since is not None:
        conditions.append(AlertDB.occurred_at >= since)
    if until is not None:
        conditions.append(AlertDB.occurred_at <= until)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = int(session.scalar(count_statement) or 0)
    records = session.scalars(
        statement.order_by(AlertDB.occurred_at.desc(), AlertDB.id).offset(offset).limit(limit)
    ).all()
    return Page[AlertRead](items=records, total=total, limit=limit, offset=offset)


@router.get("/alerts/{alert_id}", response_model=AlertRead)
def get_alert(
    alert_id: str,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[UserDB, Depends(get_current_user)],
) -> AlertRead:
    record = session.get(AlertDB, alert_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return AlertRead.model_validate(record)


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: str,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[UserDB, Depends(require_roles("admin", "analyst"))],
) -> AlertRead:
    record = session.get(AlertDB, alert_id)
    if record is None:
        raise HTTPException(status_code=404, detail="alert not found")
    if record.status != "acknowledged":
        record.status = "acknowledged"
        record.acknowledged_by_user_id = actor.id
        record.acknowledged_at = datetime.now(UTC)
        _audit(
            session,
            "alert.acknowledged",
            actor_user_id=actor.id,
            target_type="alert",
            target_id=record.id,
        )
        session.commit()
    return AlertRead.model_validate(record)
