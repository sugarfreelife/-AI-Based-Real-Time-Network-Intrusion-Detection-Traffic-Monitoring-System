from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nids_engine.features import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    FeatureSchemaError,
    FeatureVector,
    extract_features,
    validate_model_schema,
)
from nids_engine.flows import Endpoint, FinalizationReason, FlowBuilder
from nids_engine.packet import PacketMetadata


def packet(
    *,
    second: float,
    src: str | None = "192.0.2.1",
    dst: str | None = "198.51.100.2",
    sport: int | None = 12345,
    dport: int | None = 443,
    protocol: str = "TCP",
    length: int = 60,
    flags: int | None = 0x02,
) -> PacketMetadata:
    return PacketMetadata(
        timestamp=datetime.fromtimestamp(second, tz=UTC),
        src_ip=src,
        dst_ip=dst,
        src_port=sport,
        dst_port=dport,
        protocol=protocol,  # type: ignore[arg-type]
        packet_length=length,
        ip_version=4 if src and "." in src else 6 if src else None,
        tcp_flags=flags,
    )


def test_reverse_packets_join_one_flow_with_directional_stats() -> None:
    builder = FlowBuilder()
    assert builder.process(packet(second=1000.0, flags=0x02)) == []
    assert builder.process(packet(second=1001.0, src="198.51.100.2", dst="192.0.2.1", sport=443, dport=12345, flags=0x10, length=70)) == []

    [flow] = builder.flush()

    assert flow.endpoint_a == Endpoint("192.0.2.1", 12345)
    assert flow.endpoint_b == Endpoint("198.51.100.2", 443)
    assert flow.forward.packet_count == 1
    assert flow.reverse.packet_count == 1
    assert flow.forward.byte_count == 60
    assert flow.reverse.byte_count == 70
    assert flow.total_packets == 2
    assert flow.total_bytes == 130
    assert flow.tcp_syn_count == flow.tcp_ack_count == 1
    assert flow.duration_seconds == 1.0
    assert flow.finalization_reason is FinalizationReason.END_OF_CAPTURE


def test_idle_timeout_closes_before_later_packet_is_added() -> None:
    builder = FlowBuilder(idle_timeout_seconds=10, active_timeout_seconds=100)
    builder.process(packet(second=1000.0))

    finalized = builder.process(packet(second=1010.0))

    assert len(finalized) == 1
    assert finalized[0].finalization_reason is FinalizationReason.IDLE_TIMEOUT
    assert finalized[0].ended_at == datetime.fromtimestamp(1010.0, tz=UTC)
    assert builder.active_count == 1
    assert builder.flush()[0].flow_id == "flow-0000000002"


def test_active_timeout_closes_long_running_flow() -> None:
    builder = FlowBuilder(idle_timeout_seconds=100, active_timeout_seconds=10)
    builder.process(packet(second=1000.0))

    finalized = builder.process(packet(second=1010.0))

    assert len(finalized) == 1
    assert finalized[0].finalization_reason is FinalizationReason.ACTIVE_TIMEOUT
    assert finalized[0].duration_seconds == 0.0


def test_out_of_order_timestamps_do_not_move_watermark_backwards() -> None:
    builder = FlowBuilder(idle_timeout_seconds=20, active_timeout_seconds=100)
    builder.process(packet(second=1002.0))
    builder.process(packet(second=1000.0, length=80))

    [flow] = builder.flush()

    assert builder.watermark == datetime.fromtimestamp(1002.0, tz=UTC)
    assert flow.started_at == datetime.fromtimestamp(1000.0, tz=UTC)
    assert flow.last_seen_at == datetime.fromtimestamp(1002.0, tz=UTC)
    assert flow.duration_seconds == 2.0
    assert flow.total_packets == 2


def test_late_packet_that_moves_start_past_active_deadline_finalizes() -> None:
    builder = FlowBuilder(idle_timeout_seconds=100, active_timeout_seconds=10)
    builder.process(packet(second=1002.0))

    finalized = builder.process(packet(second=990.0))

    assert len(finalized) == 1
    assert finalized[0].finalization_reason is FinalizationReason.ACTIVE_TIMEOUT
    assert finalized[0].started_at == datetime.fromtimestamp(990.0, tz=UTC)


def test_repeated_packets_count_each_observation() -> None:
    builder = FlowBuilder()
    sample = packet(second=1000.0, length=64)
    builder.process(sample)
    builder.process(sample)

    [flow] = builder.flush()

    assert flow.total_packets == 2
    assert flow.total_bytes == 128
    assert flow.duration_seconds == 0.0


def test_packets_without_both_ip_endpoints_are_not_grouped() -> None:
    builder = FlowBuilder()
    builder.process(packet(second=1000.0, src=None, dst=None, sport=None, dport=None, protocol="OTHER", flags=None))
    builder.process(packet(second=1001.0, src=None, dst=None, sport=None, dport=None, protocol="OTHER", flags=None))

    flows = builder.flush()

    assert len(flows) == 2
    assert all(flow.total_packets == 1 for flow in flows)
    assert all(flow.endpoint_a.ip is None and flow.endpoint_b.ip is None for flow in flows)


def test_capacity_limit_finalizes_oldest_flow() -> None:
    builder = FlowBuilder(max_active_flows=1)
    builder.process(packet(second=1000.0))

    finalized = builder.process(packet(second=1001.0, dst="203.0.113.3"))

    assert len(finalized) == 1
    assert finalized[0].finalization_reason is FinalizationReason.CAPACITY
    assert builder.active_count == 1


def test_expiration_heap_stays_bounded_for_long_active_flow() -> None:
    builder = FlowBuilder(idle_timeout_seconds=1000, active_timeout_seconds=2000)
    for offset in range(200):
        builder.process(packet(second=1000.0 + offset / 10, flags=0x10))

    assert builder.active_count == 1
    assert len(builder._expiry_heap) <= 64


def test_empty_flush_and_positive_timeout_validation() -> None:
    builder = FlowBuilder()
    assert builder.flush() == []
    with pytest.raises(ValueError, match="idle_timeout"):
        FlowBuilder(idle_timeout_seconds=0)
    with pytest.raises(ValueError, match="max_active_flows"):
        FlowBuilder(max_active_flows=0)


def test_feature_schema_is_ordered_finite_and_marks_missing_values() -> None:
    builder = FlowBuilder()
    builder.process(packet(second=1000.0, sport=None, dport=None, protocol="ICMP", flags=None))
    [flow] = builder.flush()

    vector = extract_features(flow)
    features = vector.as_dict()

    assert vector.schema_version == FEATURE_SCHEMA_VERSION
    assert vector.feature_names == FEATURE_NAMES
    assert len(vector.values) == len(FEATURE_NAMES)
    assert all(value == value and abs(value) != float("inf") for value in vector.values)
    assert features["flow_duration_seconds"] == 0.0
    assert features["packets_per_second"] == 0.0
    assert features["bytes_per_second"] == 0.0
    assert features["protocol_icmp"] == 1.0
    assert features["endpoint_a_port_missing"] == 1.0
    assert features["endpoint_b_port_missing"] == 1.0
    assert features["reverse_packet_size_missing"] == 1.0
    assert "src_ip" not in features and "flow_id" not in features


def test_model_schema_mismatch_and_nonfinite_vectors_are_rejected() -> None:
    with pytest.raises(FeatureSchemaError, match="schema"):
        validate_model_schema("0.9", FEATURE_NAMES)
    with pytest.raises(FeatureSchemaError, match="ordering"):
        validate_model_schema(FEATURE_SCHEMA_VERSION, tuple(reversed(FEATURE_NAMES)))
    with pytest.raises(FeatureSchemaError, match="non-finite"):
        FeatureVector(FEATURE_SCHEMA_VERSION, FEATURE_NAMES, tuple(float("nan") for _ in FEATURE_NAMES))
    builder = FlowBuilder()
    builder.process(packet(second=1000.0))
    [flow] = builder.flush()
    valid = list(extract_features(flow).values)

    negative = valid.copy()
    negative[FEATURE_NAMES.index("total_bytes")] = -1.0
    with pytest.raises(FeatureSchemaError, match="negative"):
        FeatureVector(FEATURE_SCHEMA_VERSION, FEATURE_NAMES, tuple(negative))

    invalid_protocol = valid.copy()
    invalid_protocol[FEATURE_NAMES.index("protocol_udp")] = 1.0
    with pytest.raises(FeatureSchemaError, match="protocol"):
        FeatureVector(FEATURE_SCHEMA_VERSION, FEATURE_NAMES, tuple(invalid_protocol))

    invalid_type = valid.copy()
    invalid_type[FEATURE_NAMES.index("average_packet_size")] = "large"  # type: ignore[assignment]
    with pytest.raises(FeatureSchemaError, match="non-numeric"):
        FeatureVector(FEATURE_SCHEMA_VERSION, FEATURE_NAMES, tuple(invalid_type))

    invalid_port = valid.copy()
    invalid_port[FEATURE_NAMES.index("endpoint_a_port")] = 70000.0
    with pytest.raises(FeatureSchemaError, match="port range"):
        FeatureVector(FEATURE_SCHEMA_VERSION, FEATURE_NAMES, tuple(invalid_port))


def test_flush_uses_utc_timestamps_and_feature_order_is_reproducible() -> None:
    builder_a = FlowBuilder()
    builder_b = FlowBuilder()
    rows = [packet(second=1000.0), packet(second=1001.0, src="198.51.100.2", dst="192.0.2.1", sport=443, dport=12345)]
    for row in rows:
        builder_a.process(row)
        builder_b.process(row)

    [flow_a] = builder_a.flush()
    [flow_b] = builder_b.flush()

    vector_a = extract_features(flow_a)
    vector_b = extract_features(flow_b)
    assert flow_a.started_at.tzinfo is UTC
    assert vector_a.values == vector_b.values
    assert vector_a.feature_names == vector_b.feature_names
