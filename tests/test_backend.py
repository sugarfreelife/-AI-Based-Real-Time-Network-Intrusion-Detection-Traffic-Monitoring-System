from __future__ import annotations

import json
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient
from scapy.layers.inet import IP, TCP
from scapy.utils import wrpcap
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.config import Settings
from backend.app.database.models import AlertDB, AuditEventDB, CaptureRunDB, FlowRecordDB, PredictionDB, RefreshSessionDB, UserDB
from backend.app.main import create_app
from backend.app.security import hash_password, verify_password
from backend.app.services.ingestion import persist_observation
from nids_engine.detection import AlertEngine
from nids_engine.flows import FlowBuilder
from nids_engine.inference import ModelArtifactStatus, PredictionResult
from nids_engine.monitor import main as monitor_main
from nids_engine.packet import PacketMetadata

TEST_SETTINGS = Settings(database_url="sqlite+pysqlite://", jwt_secret_key="test-only-signing-key-at-least-32-bytes-long")
TEST_PASSWORD = "correct-horse-battery-42"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _observation():
    builder = FlowBuilder()
    for second in (1_700_000_000, 1_700_000_001):
        builder.process(PacketMetadata(
            timestamp=datetime.fromtimestamp(second, tz=UTC),
            src_ip="192.0.2.1",
            dst_ip="198.51.100.2",
            src_port=42000,
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
    alerts = AlertEngine(syn_burst_threshold=2, high_packet_rate_threshold=1_000_000).evaluate(flow, prediction)
    return flow, prediction, alerts


def _authenticated_client(session_factory, role: str = "admin"):
    with session_factory() as session:
        user = UserDB(
            username=f"test-{role}",
            password_hash=hash_password(TEST_PASSWORD),
            role=role,
        )
        session.add(user)
        session.commit()
    client = TestClient(create_app(session_factory, TEST_SETTINGS))
    response = client.post("/api/v1/auth/token", json={"username": user.username, "password": TEST_PASSWORD})
    assert response.status_code == 200
    tokens = response.json()
    client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
    return client, tokens


def test_atomic_observation_is_exposed_by_paginated_filtered_api(session_factory) -> None:
    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        stored = persist_observation(
            session,
            capture_id="capture-1",
            flow=flow,
            prediction=prediction,
            alerts=alerts,
        )
        flow_record_id = stored.record.id

    client, _tokens = _authenticated_client(session_factory)
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready", "database": "available"}

    page = client.get("/api/v1/flows", params={"limit": 10, "protocol": "tcp"})
    assert page.status_code == 200
    payload = page.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == flow_record_id
    assert payload["items"][0]["prediction"]["status"] == "model_missing"
    assert payload["items"][0]["endpoint_a"]["ip"] == "192.0.2.1"
    assert payload["items"][0]["ended_at"].endswith("Z")

    alert_page = client.get("/api/v1/alerts", params={"severity": "medium", "status": "new"})
    assert alert_page.status_code == 200
    assert alert_page.json()["total"] == 1
    assert alert_page.json()["items"][0]["flow_record_id"] == flow_record_id
    assert alert_page.json()["items"][0]["detection_code"] == "tcp_syn_burst"

    assert client.get(f"/api/v1/flows/{flow_record_id}").status_code == 200
    assert client.get("/api/v1/flows/missing-id").status_code == 404
    assert client.get("/api/v1/alerts/missing-id").status_code == 404


def test_api_rejects_invalid_pagination_filters_and_time_ranges(session_factory) -> None:
    client, _tokens = _authenticated_client(session_factory)
    assert client.get("/api/v1/flows", params={"limit": 101}).status_code == 422
    assert client.get("/api/v1/flows", params={"offset": -1}).status_code == 422
    assert client.get("/api/v1/flows", params={"protocol": "BOGUS"}).status_code == 422
    assert client.get(
        "/api/v1/alerts",
        params={"since": "2025-01-02T00:00:00Z", "until": "2025-01-01T00:00:00Z"},
    ).status_code == 422
    assert client.get("/api/v1/alerts", params={"since": "2025-01-01T00:00:00"}).status_code == 422


def test_database_readiness_reports_degraded_state() -> None:
    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            raise OperationalError("SELECT 1", {}, RuntimeError("database offline"))

    client = TestClient(create_app(lambda: BrokenSession()))  # type: ignore[arg-type]
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_duplicate_capture_flow_is_idempotent(session_factory) -> None:
    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        first = persist_observation(
            session,
            capture_id="same-capture",
            flow=flow,
            prediction=prediction,
            alerts=alerts,
        )

    with session_factory() as session, session.begin():
        retry = persist_observation(
            session,
            capture_id="same-capture",
            flow=flow,
            prediction=prediction,
            alerts=alerts,
        )

    assert first.created is True
    assert retry.created is False
    assert retry.record.id == first.record.id

    with session_factory() as session:
        assert session.query(FlowRecordDB).count() == 1
        assert session.query(PredictionDB).count() == 1
        assert session.query(AlertDB).count() == len(alerts)


def test_capture_flow_identity_rejects_conflicting_data_atomically(session_factory) -> None:
    from dataclasses import replace

    from backend.app.services.ingestion import IngestionConflict

    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        persist_observation(
            session,
            capture_id="conflicting-capture",
            flow=flow,
            prediction=prediction,
            alerts=alerts,
        )

    conflicting_flow = replace(flow, forward=replace(flow.forward, byte_count=flow.forward.byte_count + 1))
    with pytest.raises(IngestionConflict, match="different flow data"):
        with session_factory() as session, session.begin():
            persist_observation(
                session,
                capture_id="conflicting-capture",
                flow=conflicting_flow,
                prediction=prediction,
                alerts=alerts,
            )

    with session_factory() as session:
        assert session.query(FlowRecordDB).count() == 1
        assert session.query(PredictionDB).count() == 1
        assert session.query(AlertDB).count() == len(alerts)


def test_monitor_persists_flow_prediction_and_alert_then_api_reads_it(tmp_path, capsys) -> None:
    pcap_path = tmp_path / "capture.pcap"
    database_path = tmp_path / "observations.sqlite3"
    wrpcap(
        str(pcap_path),
        [
            IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=42000, dport=443, flags="S"),
            IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=42000, dport=443, flags="S"),
        ],
    )
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    result = monitor_main([
        "--pcap", str(pcap_path),
        "--database-url", f"sqlite+pysqlite:///{database_path}",
        "--syn-burst-threshold", "2",
        "--high-packets-per-second", "1000000",
    ])

    captured = capsys.readouterr()
    flow_output = json.loads(captured.out.strip().splitlines()[0])
    summary = json.loads(captured.err.strip())["monitor_summary"]
    assert result == 0
    assert summary["persisted"] is True
    assert summary["flows"] == 1
    assert flow_output["prediction"]["status"] == "model_missing"
    capture_id = summary["capture_id"]

    persisted_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    persisted_factory = sessionmaker(bind=persisted_engine, expire_on_commit=False)
    with persisted_factory() as session:
        assert session.query(FlowRecordDB).count() == 1
        assert session.query(PredictionDB).count() == 1
        assert session.query(AlertDB).count() == 1
        [capture_run] = session.query(CaptureRunDB).all()
        assert capture_run.status == "completed"
        assert capture_run.source_name == "capture.pcap"
        assert capture_run.packets_seen == 2
        assert capture_run.packets_processed == 2
        assert capture_run.flow_count == 1
        assert capture_run.alert_count == 1
        assert capture_run.completed_at is not None
    client, _tokens = _authenticated_client(persisted_factory)
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json()["items"][0]["detection_code"] == "tcp_syn_burst"

    retry_result = monitor_main([
        "--pcap", str(pcap_path),
        "--database-url", f"sqlite+pysqlite:///{database_path}",
        "--capture-id", capture_id,
        "--syn-burst-threshold", "2",
        "--high-packets-per-second", "1000000",
    ])
    retry_output = capsys.readouterr()
    retry_summary = json.loads(retry_output.err.strip())["monitor_summary"]
    assert retry_result == 0
    assert retry_summary["flows"] == 1
    assert retry_summary["duplicate_flows"] == 1
    with persisted_factory() as session:
        [capture_run] = session.query(CaptureRunDB).all()
        assert capture_run.attempt_count == 2
        assert capture_run.duplicate_flows == 1
        assert session.query(FlowRecordDB).count() == 1
        assert session.query(PredictionDB).count() == 1
        assert session.query(AlertDB).count() == 1
    persisted_engine.dispose()


def test_monitor_stops_and_reports_when_database_schema_is_missing(tmp_path, capsys) -> None:
    pcap_path = tmp_path / "capture.pcap"
    database_path = tmp_path / "unmigrated.sqlite3"
    wrpcap(
        str(pcap_path),
        [IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=42000, dport=443, flags="S")],
    )

    result = monitor_main([
        "--pcap", str(pcap_path),
        "--database-url", f"sqlite+pysqlite:///{database_path}",
    ])

    captured = capsys.readouterr()
    error = json.loads(captured.err.strip())
    assert result == 1
    assert captured.out == ""
    assert error["completed_flows"] == 0
    assert "database write failed" in error["monitor_error"]


def test_api_requires_valid_short_lived_access_token(session_factory) -> None:
    client = TestClient(create_app(session_factory, TEST_SETTINGS))
    assert client.get("/api/v1/flows").status_code == 401
    assert client.get("/api/v1/alerts", headers={"Authorization": "Bearer malformed"}).status_code == 401
    assert client.get("/health/live").status_code == 200


def test_dashboard_cors_allows_configured_origin_without_cookies(session_factory) -> None:
    config = Settings(
        database_url="sqlite+pysqlite://",
        jwt_secret_key=TEST_SETTINGS.jwt_secret_key,
        cors_origins=("http://localhost:5173",),
    )
    client = TestClient(create_app(session_factory, config))
    response = client.options(
        "/api/v1/alerts",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers

    blocked = client.get("/health/live", headers={"Origin": "https://untrusted.example"})
    assert blocked.status_code == 200
    assert "access-control-allow-origin" not in blocked.headers


def test_login_fails_closed_without_jwt_secret(session_factory) -> None:
    client = TestClient(create_app(session_factory, Settings(database_url="sqlite+pysqlite://")))
    response = client.post("/api/v1/auth/token", json={"username": "nobody", "password": "irrelevant"})
    assert response.status_code == 503


def test_argon2id_login_and_failed_login_are_audited(session_factory) -> None:
    client, _tokens = _authenticated_client(session_factory)
    with session_factory() as session:
        user = session.scalar(select(UserDB).where(UserDB.username == "test-admin"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password(TEST_PASSWORD, user.password_hash)
        assert user.password_hash != TEST_PASSWORD

    failed = client.post("/api/v1/auth/token", json={"username": "test-admin", "password": "wrong-password"})
    assert failed.status_code == 401
    assert client.get("/api/v1/auth/me").json()["role"] == "admin"
    with session_factory() as session:
        event_types = set(session.scalars(select(AuditEventDB.event_type)).all())
        assert "auth.login_succeeded" in event_types
        assert "auth.login_failed" in event_types
        assert session.query(RefreshSessionDB).count() == 1


def test_refresh_rotates_tokens_and_detects_reuse(session_factory) -> None:
    client, tokens = _authenticated_client(session_factory)
    second_session = client.post(
        "/api/v1/auth/token",
        json={"username": "test-admin", "password": TEST_PASSWORD},
    ).json()
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    next_tokens = rotated.json()
    assert next_tokens["refresh_token"] != tokens["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second_session["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": next_tokens["refresh_token"]}).status_code == 401
    with session_factory() as session:
        events = session.scalars(select(AuditEventDB.event_type)).all()
        assert "auth.refresh_reuse_detected" in events
        assert session.query(RefreshSessionDB).filter(RefreshSessionDB.revoked_at.is_(None)).count() == 0


def test_logout_revokes_refresh_token(session_factory) -> None:
    client, tokens = _authenticated_client(session_factory)
    response = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    # Access tokens remain valid until their short expiry, while refresh is revoked immediately.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_admin_user_creation_and_role_protected_alert_acknowledgement(session_factory) -> None:
    admin_client, _ = _authenticated_client(session_factory, role="admin")
    create = admin_client.post(
        "/api/v1/auth/users",
        json={"username": "Analyst.One", "password": "a-secure-test-password", "role": "analyst"},
    )
    assert create.status_code == 201
    assert create.json()["username"] == "analyst.one"
    assert "password_hash" not in create.json()
    assert admin_client.post(
        "/api/v1/auth/users",
        json={"username": "analyst.one", "password": "a-secure-test-password", "role": "viewer"},
    ).status_code == 409

    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        saved_flow = persist_observation(session, capture_id="ack-capture", flow=flow, prediction=prediction, alerts=alerts)
        flow_record_id = saved_flow.record.id
        alert_id = alerts[0].alert_id
    viewer_client, _ = _authenticated_client(session_factory, role="viewer")
    assert viewer_client.get("/api/v1/flows").status_code == 200
    assert viewer_client.patch(f"/api/v1/alerts/{alert_id}/acknowledge").status_code == 403
    assert viewer_client.post(
        "/api/v1/auth/users",
        json={"username": "viewer.created", "password": "a-secure-test-password", "role": "viewer"},
    ).status_code == 403
    analyst_client, _ = _authenticated_client(session_factory, role="analyst")
    ack = analyst_client.patch(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_by_user_id"] is not None
    with session_factory() as session, session.begin():
        retry = persist_observation(
            session, capture_id="ack-capture", flow=flow, prediction=prediction, alerts=alerts
        )
        assert retry.created is False
        assert retry.record.alerts[0].status == "acknowledged"
    with session_factory() as session:
        event = session.scalar(select(AuditEventDB).where(AuditEventDB.event_type == "alert.acknowledged"))
        assert event is not None and event.target_id == alert_id
        denied = session.scalar(select(AuditEventDB).where(AuditEventDB.event_type == "auth.authorization_denied"))
        assert denied is not None and denied.actor_user_id is not None
        assert session.get(FlowRecordDB, flow_record_id) is not None


def test_initial_admin_command_creates_an_argon2id_user(session_factory, monkeypatch, capsys) -> None:
    from backend.app import auth_admin

    monkeypatch.setattr(auth_admin, "SessionLocal", session_factory)
    monkeypatch.setattr(auth_admin, "settings", TEST_SETTINGS)
    answers = iter([TEST_PASSWORD, TEST_PASSWORD])
    monkeypatch.setattr("builtins.input", lambda _prompt: "first.admin")
    monkeypatch.setattr("backend.app.auth_admin.getpass", lambda _prompt: next(answers))
    assert auth_admin.main([]) == 0
    assert "Created administrator" in capsys.readouterr().out
    with session_factory() as session:
        admin = session.scalar(select(UserDB).where(UserDB.username == "first.admin"))
        assert admin is not None and admin.role == "admin"
        assert admin.password_hash.startswith("$argon2id$")
        event = session.scalar(select(AuditEventDB).where(AuditEventDB.event_type == "user.bootstrap_admin"))
        assert event is not None and event.target_id == admin.id


def test_authenticated_websocket_delivers_new_persisted_alert(session_factory) -> None:
    client, tokens = _authenticated_client(session_factory)
    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        saved_flow = persist_observation(session, capture_id="ws-capture", flow=flow, prediction=prediction, alerts=alerts)
        flow_record_id = saved_flow.record.id
        original_alert_id = alerts[0].alert_id
    with session_factory() as session:
        original_alert = session.get(AlertDB, original_alert_id)
        assert original_alert is not None
        resume_cursor = {
            "after_created_at": original_alert.created_at.isoformat(),
            "after_id": original_alert.id,
        }

    with client.websocket_connect("/api/v1/ws/alerts") as websocket:
        websocket.send_json({"access_token": tokens["access_token"], **resume_cursor})
        assert websocket.receive_json()["type"] == "ready"
        with session_factory() as session, session.begin():
            session.add(AlertDB(
                id="websocket-alert",
                flow_record_id=flow_record_id,
                detection_code="websocket_test",
                source="test",
                severity="low",
                title="Persisted test alert",
                explanation="Controlled WebSocket delivery fixture.",
                occurred_at=datetime.now(UTC),
                protocol="TCP",
                endpoint_a={"ip": "192.0.2.1", "port": 42000},
                endpoint_b={"ip": "198.51.100.2", "port": 443},
                model_version=None,
                evidence={},
                status="new",
            ))
        message = websocket.receive_json()
        assert message["type"] == "alert"
        assert message["data"]["id"] == "websocket-alert"


def test_websocket_rejects_invalid_first_message(session_factory) -> None:
    from starlette.websockets import WebSocketDisconnect

    client = TestClient(create_app(session_factory, TEST_SETTINGS))
    with client.websocket_connect("/api/v1/ws/alerts") as websocket:
        websocket.send_json({})
        with pytest.raises(WebSocketDisconnect) as disconnected:
            websocket.receive_json()
    assert disconnected.value.code == 4401


def test_websocket_rejects_non_json_authentication_frame(session_factory) -> None:
    from starlette.websockets import WebSocketDisconnect

    client = TestClient(create_app(session_factory, TEST_SETTINGS))
    with client.websocket_connect("/api/v1/ws/alerts") as websocket:
        websocket.send_text("not-json")
        with pytest.raises(WebSocketDisconnect) as disconnected:
            websocket.receive_json()
    assert disconnected.value.code == 4401


def test_websocket_closes_when_alert_storage_fails(session_factory) -> None:
    from starlette.websockets import WebSocketDisconnect

    client, tokens = _authenticated_client(session_factory)
    factory_calls = 0

    def fail_during_polling():
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls > 1:
            raise OperationalError("SELECT alerts", {}, RuntimeError("database offline"))
        return session_factory()

    client.app.state.session_factory = fail_during_polling
    with client.websocket_connect("/api/v1/ws/alerts") as websocket:
        websocket.send_json({"access_token": tokens["access_token"]})
        assert websocket.receive_json()["type"] == "ready"
        with pytest.raises(WebSocketDisconnect) as disconnected:
            websocket.receive_json()
    assert disconnected.value.code == 1011
