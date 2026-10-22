from __future__ import annotations

import json
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient
from scapy.layers.inet import IP, TCP
from scapy.utils import wrpcap
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.models import AlertDB, FlowRecordDB, PredictionDB
from backend.app.main import create_app
from backend.app.services.ingestion import persist_observation
from nids_engine.detection import AlertEngine
from nids_engine.flows import FlowBuilder
from nids_engine.inference import ModelArtifactStatus, PredictionResult
from nids_engine.monitor import main as monitor_main
from nids_engine.packet import PacketMetadata


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
        flow_record_id = stored.id

    client = TestClient(create_app(session_factory))
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
    client = TestClient(create_app(session_factory))
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


def test_duplicate_capture_flow_rolls_back_the_entire_observation(session_factory) -> None:
    flow, prediction, alerts = _observation()
    with session_factory() as session, session.begin():
        persist_observation(
            session,
            capture_id="same-capture",
            flow=flow,
            prediction=prediction,
            alerts=alerts,
        )

    with pytest.raises(IntegrityError):
        with session_factory() as session, session.begin():
            persist_observation(
                session,
                capture_id="same-capture",
                flow=flow,
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

    persisted_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    persisted_factory = sessionmaker(bind=persisted_engine, expire_on_commit=False)
    with persisted_factory() as session:
        assert session.query(FlowRecordDB).count() == 1
        assert session.query(PredictionDB).count() == 1
        assert session.query(AlertDB).count() == 1
    response = TestClient(create_app(persisted_factory)).get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json()["items"][0]["detection_code"] == "tcp_syn_burst"
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
