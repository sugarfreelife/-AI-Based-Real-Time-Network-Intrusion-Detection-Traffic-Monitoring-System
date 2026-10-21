from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6, ICMPv6EchoRequest
from scapy.packet import Raw
from scapy.utils import PcapNgWriter, wrpcap

from nids_engine.capture import CaptureError, replay_pcap
from nids_engine.packet import PacketParseError, parse_packet


def _timestamp(packet: object, seconds: float = 1_800_000_000.25) -> object:
    packet.time = seconds  # type: ignore[attr-defined]
    return packet


def test_parses_ipv4_tcp_and_flags_without_payload() -> None:
    packet = _timestamp(IP(src="192.0.2.10", dst="198.51.100.20") / TCP(sport=50123, dport=443, flags="SA") / Raw(b"secret"))

    result = parse_packet(packet)

    assert result.timestamp == datetime.fromtimestamp(1_800_000_000.25, tz=UTC)
    assert (result.src_ip, result.dst_ip) == ("192.0.2.10", "198.51.100.20")
    assert (result.src_port, result.dst_port) == (50123, 443)
    assert result.protocol == "TCP"
    assert result.ip_version == 4
    assert result.tcp_flags == 0x12
    assert result.packet_length == len(packet)
    assert not hasattr(result, "payload")


def test_parses_ipv6_udp() -> None:
    packet = _timestamp(IPv6(src="2001:db8::1", dst="2001:db8::2") / UDP(sport=53, dport=5353))

    result = parse_packet(packet)

    assert result.protocol == "UDP"
    assert result.ip_version == 6
    assert (result.src_port, result.dst_port) == (53, 5353)


def test_parses_icmp_without_ports() -> None:
    result = parse_packet(_timestamp(IP(src="192.0.2.1", dst="192.0.2.2") / ICMP()))

    assert result.protocol == "ICMP"
    assert result.src_port is None
    assert result.dst_port is None


def test_parses_icmpv6() -> None:
    result = parse_packet(_timestamp(IPv6(src="2001:db8::1", dst="2001:db8::2") / ICMPv6EchoRequest()))

    assert result.protocol == "ICMPV6"
    assert result.src_port is None


def test_non_ip_packet_is_retained_as_other() -> None:
    result = parse_packet(_timestamp(Raw(b"opaque frame")))

    assert result.protocol == "OTHER"
    assert result.src_ip is None
    assert result.dst_ip is None
    assert result.packet_length == len(b"opaque frame")


def test_invalid_timestamp_is_reported() -> None:
    packet = IP() / TCP()
    packet.time = float("nan")

    with pytest.raises(PacketParseError, match="timestamp"):
        parse_packet(packet)


def test_replays_pcap_incrementally_and_reports_stats(tmp_path) -> None:
    path = tmp_path / "controlled.pcap"
    packets = [
        _timestamp(IP(src="192.0.2.1", dst="192.0.2.2") / TCP(sport=1, dport=2)),
        _timestamp(IP(src="192.0.2.2", dst="192.0.2.1") / UDP(sport=2, dport=1), 1_800_000_001.25),
    ]
    wrpcap(str(path), packets)
    seen = []

    stats = replay_pcap(path, seen.append)

    assert [row.protocol for row in seen] == ["TCP", "UDP"]
    assert stats.status == "completed"
    assert stats.packets_seen == 2
    assert stats.packets_processed == 2
    assert stats.parsing_failures == 0
    assert stats.started_at is not None and stats.started_at.tzinfo is UTC


def test_replays_pcapng(tmp_path) -> None:
    path = tmp_path / "controlled.pcapng"
    writer = PcapNgWriter(str(path))
    writer.write(_timestamp(IP(src="192.0.2.9", dst="198.51.100.9") / TCP(dport=8443)))
    writer.close()
    seen = []

    stats = replay_pcap(path, seen.append)

    assert stats.status == "completed"
    assert len(seen) == 1
    assert seen[0].protocol == "TCP"
    assert seen[0].dst_port == 8443


def test_protocol_filter_counts_omitted_packets(tmp_path) -> None:
    path = tmp_path / "filtered.pcap"
    wrpcap(
        str(path),
        [
            _timestamp(IP() / TCP()),
            _timestamp(IP() / UDP(), 1_800_000_001.0),
        ],
    )
    seen = []

    stats = replay_pcap(path, seen.append, protocols=["udp"])

    assert [row.protocol for row in seen] == ["UDP"]
    assert stats.packets_seen == 2
    assert stats.packets_processed == 1
    assert stats.packets_filtered == 1


def test_parse_failure_does_not_stop_following_packets(tmp_path, monkeypatch) -> None:
    from nids_engine import capture

    path = tmp_path / "continues.pcap"
    wrpcap(
        str(path),
        [_timestamp(IP() / TCP()), _timestamp(IP() / UDP(), 1_800_000_001.0)],
    )
    real_parse = capture.parse_packet
    calls = 0

    def fail_once(packet: object):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PacketParseError("controlled malformed packet")
        return real_parse(packet)

    monkeypatch.setattr(capture, "parse_packet", fail_once)
    seen = []

    stats = replay_pcap(path, seen.append)

    assert len(seen) == 1 and seen[0].protocol == "UDP"
    assert stats.packets_seen == 2
    assert stats.packets_processed == 1
    assert stats.parsing_failures == 1


def test_missing_pcap_raises_clear_error(tmp_path) -> None:
    with pytest.raises(CaptureError, match="could not open PCAP"):
        replay_pcap(tmp_path / "missing.pcap", lambda _packet: None)


def test_cli_replay_decodes_packet_in_fresh_process_and_omits_payload(tmp_path) -> None:
    path = tmp_path / "cli.pcap"
    wrpcap(
        str(path),
        [_timestamp(IP(src="192.0.2.10", dst="198.51.100.20") / TCP(dport=443) / Raw(b"private-data"))],
    )

    completed = subprocess.run(
        [sys.executable, "-m", "nids_engine.replay", "--pcap", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    packet_record = json.loads(completed.stdout.splitlines()[0])
    assert packet_record["protocol"] == "TCP"
    assert packet_record["src_ip"] == "192.0.2.10"
    assert "private-data" not in completed.stdout
