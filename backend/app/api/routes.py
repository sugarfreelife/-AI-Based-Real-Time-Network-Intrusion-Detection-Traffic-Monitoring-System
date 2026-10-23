"""Validated, authenticated REST resources for persisted flow observations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.auth import _audit, get_current_user, require_roles
from backend.app.database.models import AlertDB, CaptureRunDB, FlowRecordDB, UserDB
from backend.app.database.session import get_session
from backend.app.schemas import AlertRead, CaptureRunRead, FlowRead, Page

router = APIRouter(prefix="/api/v1")

CaptureStatus = Literal["running", "completed", "partial", "failed"]


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
