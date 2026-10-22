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
from backend.app.database.models import AlertDB, AuditEventDB, FlowRecordDB, UserDB
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
                flow_record_id = stored.id
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
            session.execute(delete(FlowRecordDB).where(FlowRecordDB.capture_id == capture_id))
            if user_id is not None:
                session.execute(delete(AuditEventDB).where(AuditEventDB.actor_user_id == user_id))
                session.execute(delete(AuditEventDB).where(AuditEventDB.target_id == user_id))
                session.execute(delete(UserDB).where(UserDB.id == user_id))
        engine.dispose()
