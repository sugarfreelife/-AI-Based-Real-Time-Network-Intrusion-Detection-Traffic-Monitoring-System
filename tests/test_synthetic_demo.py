from __future__ import annotations

import json

from nids_engine.monitor import main as monitor_main
from scripts.synthetic_demo import build_packets, write_capture


def test_synthetic_capture_is_explicitly_labelled_and_triggers_only_rule_alerts(tmp_path, capsys) -> None:
    capture_path = tmp_path / "synthetic-demo-not-real-network.pcap"
    packets = build_packets(flows=2, syn_per_flow=24)
    assert len(packets) == 48
    assert all(packet["IP"].src == "203.0.113.10" for packet in packets)

    assert write_capture(capture_path, flows=2, syn_per_flow=24) == 48
    assert monitor_main(["--pcap", str(capture_path)]) == 0

    captured = capsys.readouterr()
    output = [json.loads(line) for line in captured.out.splitlines()]
    summary = json.loads(captured.err)["monitor_summary"]
    assert len(output) == 2
    assert all(item["prediction"]["status"] == "model_missing" for item in output)
    assert all([alert["detection_code"] for alert in item["alerts"]] == ["tcp_syn_burst"] for item in output)
    assert summary["capture"]["packets_seen"] == 48
    assert summary["flows"] == 2
    assert summary["alerts"] == 2
