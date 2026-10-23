from __future__ import annotations

import json

from scapy.layers.inet import IP, TCP
from scapy.utils import wrpcap
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.database.models import CaptureRunDB, FlowRecordDB
from nids_engine.monitor import main as monitor_main


def test_failed_replay_is_recorded_without_storing_the_full_source_path(tmp_path, capsys) -> None:
    database_path = tmp_path / "capture-runs.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    missing_capture = tmp_path / "private-folder-name" / "missing.pcap"
    result = monitor_main([
        "--pcap", str(missing_capture),
        "--database-url", f"sqlite+pysqlite:///{database_path}",
    ])

    output = capsys.readouterr()
    error = json.loads(output.err)
    assert result == 1
    assert error["failure_reason"] == "capture_error"
    with factory() as session:
        [run] = session.query(CaptureRunDB).all()
        assert run.status == "failed"
        assert run.failure_reason == "capture_error"
        assert run.source_name == "missing.pcap"
        assert str(tmp_path) not in run.source_name
        assert run.completed_at is not None
        assert session.query(FlowRecordDB).count() == 0
    engine.dispose()


def test_partial_capture_run_records_read_failure_counts(tmp_path, capsys, monkeypatch) -> None:
    pcap_path = tmp_path / "partial.pcap"
    wrpcap(str(pcap_path), [IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=42000, dport=443, flags="S")])
    database_path = tmp_path / "partial.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    from nids_engine import monitor

    def replay_with_partial_stats(_pcap, callback):
        from datetime import UTC, datetime
        from nids_engine.capture import CaptureStats
        from nids_engine.packet import PacketMetadata

        callback(PacketMetadata(
            timestamp=datetime.now(UTC), src_ip="192.0.2.1", dst_ip="198.51.100.2",
            src_port=42000, dst_port=443, protocol="TCP", packet_length=60,
            ip_version=4, tcp_flags=0x02,
        ))
        return CaptureStats(source=str(pcap_path), status="partial", packets_seen=1,
                            packets_processed=1, read_failures=1)

    monkeypatch.setattr(monitor, "replay_pcap", replay_with_partial_stats)
    result = monitor_main(["--pcap", str(pcap_path), "--database-url", f"sqlite+pysqlite:///{database_path}"])
    capsys.readouterr()
    assert result == 1
    persisted_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    factory = sessionmaker(bind=persisted_engine, expire_on_commit=False)
    with factory() as session:
        [run] = session.query(CaptureRunDB).all()
        assert run.status == "partial"
        assert run.packets_seen == 1
        assert run.read_failures == 1
        assert run.flow_count == 1
    persisted_engine.dispose()
