"""Opt-in PostgreSQL integration coverage for an isolated *_test database."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.app.config import Settings
from backend.app.database.models import AlertDB, AuditEventDB, CaptureRunDB, FlowRecordDB, RefreshSessionDB, UserDB
from backend.app.database.session import make_engine
from backend.app.main import create_app
from backend.app.security import hash_password
from backend.app.services.ingestion import persist_observation
from nids_engine.detection import AlertEngine
from nids_engine.flows import FlowBuilder
from nids_engine.inference import ModelArtifactStatus, PredictionResult
from nids_engine.packet import PacketMetadata


pytestmark = [pytest.mark.postgres]

TEST_PASSWORD = "postgres-integration-test-password"
TEST_JWT_SECRET = "postgres-integration-jwt-secret-long-enough-for-tests"


def _enabled_test_database() -> str:
    if os.environ.get("NIDS_ENABLE_POSTGRES_TESTS") != "1":
        pytest.skip("set NIDS_ENABLE_POSTGRES_TESTS=1 to enable PostgreSQL integration tests")
    database_url = (
        os.environ.get("NIDS_TEST_POSTGRES_URL") or os.environ.get("DATABASE_URL", "")
    ).strip()
    if not database_url:
        pytest.fail("NIDS_TEST_POSTGRES_URL must point to a disposable database whose name includes 'test'")
    parsed_url = make_url(database_url)
    if "test" not in (parsed_url.database or "").lower():
        pytest.fail("refusing to run PostgreSQL integration coverage unless the database name contains 'test'")
    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail("NIDS_TEST_POSTGRES_URL must use PostgreSQL")
    return database_url


def _create_observation():
    builder = FlowBuilder()
    start = datetime.now(UTC).replace(microsecond=0)
    for offset in (0, 1):
        builder.process(PacketMetadata(
            timestamp=start + timedelta(seconds=offset),
            src_ip="192.0.2.31",
            dst_ip="198.51.100.42",
            src_port=44000,
            dst_port=443,
            protocol="TCP",
            packet_length=60,
            ip_version=4,
            tcp_flags=0x02,
        ))
    [flow] = builder.flush()
    prediction = PredictionResult(
        flow_id=flow.flow_id,
        status=ModelArtifactStatus.MISSING.value,
        predicted_label=None,
        model_version=None,
        feature_schema_version="1.0",
        predicted_at_utc=datetime.now(UTC).isoformat(),
        reason="model_unavailable",
    )
    alerts = AlertEngine(
        syn_burst_threshold=2,
        high_packet_rate_threshold=1_000_000,
    ).evaluate(flow, prediction)
    return flow, prediction, alerts


def test_postgres_auth_persistence_acknowledgement_and_websocket() -> None:
    database_url = _enabled_test_database()
    engine = make_engine(database_url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    username = f"pg-test-{suffix}"
    capture_id = str(uuid4())
    user_id: str | None = None

    try:
        with factory() as session:
            assert session.execute(text("SELECT current_database()")).scalar_one()
            user = UserDB(username=username, password_hash=hash_password(TEST_PASSWORD), role="admin")
            session.add(user)
            session.commit()
            user_id = user.id

        app = create_app(
            factory,
            Settings(database_url=database_url, jwt_secret_key=TEST_JWT_SECRET),
        )
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/token",
                json={"username": username, "password": TEST_PASSWORD},
            )
            assert login.status_code == 200
            tokens = login.json()
            client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
            assert client.get("/api/v1/auth/me").json()["username"] == username

            started_at = datetime.now(UTC)
            with factory() as session, session.begin():
                session.add(CaptureRunDB(
                    capture_id=capture_id,
                    source_name="postgres-integration.pcap",
                    status="completed",
                    started_at=started_at,
                    completed_at=started_at,
                    packets_seen=2,
                    packets_processed=2,
                    flow_count=1,
                    model_status="missing",
                ))
            history = client.get("/api/v1/captures", params={"status": "completed"})
            assert history.status_code == 200
            assert history.json()["total"] == 1
            assert history.json()["items"][0]["capture_id"] == capture_id
            assert client.get(f"/api/v1/captures/{capture_id}").json()["source_name"] == "postgres-integration.pcap"

            flow, prediction, alerts = _create_observation()
            assert alerts
            with factory() as session, session.begin():
                stored = persist_observation(
                    session,
                    capture_id=capture_id,
                    flow=flow,
                    prediction=prediction,
                    alerts=alerts,
                )
                flow_record_id = stored.record.id
            assert stored.created is True
            with factory() as session, session.begin():
                retried = persist_observation(
                    session,
                    capture_id=capture_id,
                    flow=flow,
                    prediction=prediction,
                    alerts=alerts,
                )
            assert retried.created is False
            assert retried.record.id == flow_record_id
            analytics_params = {
                "since": (started_at - timedelta(seconds=1)).isoformat(),
                "until": (started_at + timedelta(minutes=10)).isoformat(),
            }
            aggregate = client.get("/api/v1/analytics/summary", params=analytics_params)
            assert aggregate.status_code == 200
            assert aggregate.json()["flow_count"] == 1
            assert aggregate.json()["alert_count"] == len(alerts)
            assert aggregate.json()["capture_run_count"] == 1
            timeline = client.get("/api/v1/analytics/timeline", params={**analytics_params, "bucket": "hour"})
            assert timeline.status_code == 200
            assert sum(item["flow_count"] for item in timeline.json()["items"]) == 1
            assert sum(item["alert_count"] for item in timeline.json()["items"]) == len(alerts)
            assert client.get("/api/v1/flows").json()["items"][0]["id"] == flow_record_id

            alert_id = alerts[0].alert_id
            acknowledged = client.patch(f"/api/v1/alerts/{alert_id}/acknowledge")
            assert acknowledged.status_code == 200
            assert acknowledged.json()["status"] == "acknowledged"

            with factory() as session:
                original_alert = session.get(AlertDB, alert_id)
                assert original_alert is not None
                cursor = {
                    "after_created_at": original_alert.created_at.isoformat(),
                    "after_id": original_alert.id,
                }

            rotated = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
            assert rotated.status_code == 200
            assert rotated.json()["refresh_token"] != tokens["refresh_token"]

            with client.websocket_connect("/api/v1/ws/alerts") as socket:
                socket.send_json({"access_token": rotated.json()["access_token"], **cursor})
                assert socket.receive_json()["type"] == "ready"
                streamed_alert_id = str(uuid4())
                with factory() as session, session.begin():
                    session.add(AlertDB(
                        id=streamed_alert_id,
                        flow_record_id=flow_record_id,
                        detection_code="postgres_integration_stream",
                        source="test",
                        severity="low",
                        title="PostgreSQL integration stream fixture",
                        explanation="Temporary integration-test alert.",
                        occurred_at=datetime.now(UTC),
                        protocol="TCP",
                        endpoint_a={"ip": "192.0.2.31", "port": 44000},
                        endpoint_b={"ip": "198.51.100.42", "port": 443},
                        model_version=None,
                        evidence={},
                        status="new",
                    ))
                streamed_message = socket.receive_json()
                assert streamed_message["type"] == "alert"
                assert streamed_message["data"]["id"] == streamed_alert_id

            logout = client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": rotated.json()["refresh_token"]},
            )
            assert logout.status_code == 204
    finally:
        with factory.begin() as session:
            session.execute(delete(CaptureRunDB).where(CaptureRunDB.capture_id == capture_id))
            session.execute(delete(FlowRecordDB).where(FlowRecordDB.capture_id == capture_id))
            if user_id is not None:
                session.execute(delete(AuditEventDB).where(AuditEventDB.actor_user_id == user_id))
                session.execute(delete(AuditEventDB).where(AuditEventDB.target_id == user_id))
                session.execute(delete(UserDB).where(UserDB.id == user_id))
        engine.dispose()


def test_postgres_admin_user_status_protection_and_session_revocation() -> None:
    database_url = _enabled_test_database()
    engine = make_engine(database_url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    admin_username = f"pg-admin-{suffix}"
    analyst_username = f"pg-analyst-{suffix}"
    backup_username = f"pg-backup-{suffix}"
    admin_id: str | None = None
    target_ids: list[str] = []

    try:
        with factory() as session:
            admin = UserDB(username=admin_username, password_hash=hash_password(TEST_PASSWORD), role="admin")
            session.add(admin)
            session.commit()
            admin_id = admin.id

        app = create_app(factory, Settings(database_url=database_url, jwt_secret_key=TEST_JWT_SECRET))
        with TestClient(app) as admin_client:
            login = admin_client.post(
                "/api/v1/auth/token", json={"username": admin_username, "password": TEST_PASSWORD}
            )
            assert login.status_code == 200
            tokens = login.json()
            admin_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

            analyst_create = admin_client.post(
                "/api/v1/auth/users",
                json={"username": analyst_username, "password": TEST_PASSWORD, "role": "analyst"},
            )
            backup_create = admin_client.post(
                "/api/v1/auth/users",
                json={"username": backup_username, "password": TEST_PASSWORD, "role": "admin"},
            )
            assert analyst_create.status_code == backup_create.status_code == 201
            analyst_id = analyst_create.json()["id"]
            backup_id = backup_create.json()["id"]
            target_ids = [analyst_id, backup_id]

            listing = admin_client.get("/api/v1/auth/users", params={"limit": 2, "offset": 0})
            assert listing.status_code == 200
            assert listing.json()["total"] == 3
            assert len(listing.json()["items"]) == 2
            assert all("password_hash" not in item for item in listing.json()["items"])

            analyst_client = TestClient(app)
            analyst_login = analyst_client.post(
                "/api/v1/auth/token", json={"username": analyst_username, "password": TEST_PASSWORD}
            )
            assert analyst_login.status_code == 200
            analyst_tokens = analyst_login.json()
            analyst_client.headers.update({"Authorization": f"Bearer {analyst_tokens['access_token']}"})

            disabled = admin_client.patch(
                f"/api/v1/auth/users/{analyst_id}/status", json={"is_active": False}
            )
            assert disabled.status_code == 200 and disabled.json()["is_active"] is False
            assert analyst_client.get("/api/v1/auth/me").status_code == 401
            assert analyst_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": analyst_tokens["refresh_token"]}
            ).status_code == 401

            enabled = admin_client.patch(
                f"/api/v1/auth/users/{analyst_id}/status", json={"is_active": True}
            )
            assert enabled.status_code == 200 and enabled.json()["is_active"] is True
            assert admin_client.patch(
                f"/api/v1/auth/users/{backup_id}/status", json={"is_active": False}
            ).status_code == 200
            assert admin_client.patch(
                f"/api/v1/auth/users/{admin_id}/status", json={"is_active": False}
            ).status_code == 409

            with factory() as session:
                active_admins = session.query(UserDB).filter(UserDB.role == "admin", UserDB.is_active.is_(True)).count()
                events = session.query(AuditEventDB).filter(
                    AuditEventDB.event_type == "auth.user_status_changed",
                    AuditEventDB.target_id.in_([analyst_id, backup_id]),
                ).all()
                assert active_admins == 1
                assert len(events) == 3
                assert all("password" not in event.details for event in events)
    finally:
        with factory.begin() as session:
            if admin_id is not None:
                session.execute(delete(RefreshSessionDB).where(RefreshSessionDB.user_id.in_([admin_id, *target_ids])))
                session.execute(delete(AuditEventDB).where(
                    AuditEventDB.actor_user_id == admin_id,
                ))
            if target_ids:
                session.execute(delete(AuditEventDB).where(AuditEventDB.target_id.in_(target_ids)))
                session.execute(delete(UserDB).where(UserDB.id.in_(target_ids)))
            if admin_id is not None:
                session.execute(delete(UserDB).where(UserDB.id == admin_id))
        engine.dispose()
