"""Versioned, deterministic feature extraction shared by training and inference."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from nids_engine.flows import FlowRecord

FEATURE_SCHEMA_VERSION = "1.0"
FEATURE_NAMES: tuple[str, ...] = (
    "flow_duration_seconds",
    "total_packets",
    "total_bytes",
    "forward_packets",
    "reverse_packets",
    "forward_bytes",
    "reverse_bytes",
    "packets_per_second",
    "bytes_per_second",
    "average_packet_size",
    "min_packet_size",
    "max_packet_size",
    "protocol_tcp",
    "protocol_udp",
    "protocol_icmp",
    "protocol_icmpv6",
    "protocol_other",
    "endpoint_a_port",
    "endpoint_a_port_missing",
    "endpoint_b_port",
    "endpoint_b_port_missing",
    "tcp_syn_count",
    "tcp_ack_count",
    "tcp_fin_count",
    "tcp_rst_count",
    "tcp_psh_count",
    "forward_packet_size_min",
    "forward_packet_size_max",
    "forward_packet_size_missing",
    "reverse_packet_size_min",
    "reverse_packet_size_max",
    "reverse_packet_size_missing",
)


class FeatureSchemaError(ValueError):
    """Raised when a feature vector or model metadata does not match the schema."""


@dataclass(frozen=True, slots=True)
class FeatureVector:
    schema_version: str
    feature_names: tuple[str, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.schema_version != FEATURE_SCHEMA_VERSION:
            raise FeatureSchemaError(
                f"feature schema {self.schema_version!r} does not match {FEATURE_SCHEMA_VERSION!r}"
            )
        if self.feature_names != FEATURE_NAMES:
            raise FeatureSchemaError("feature names or ordering do not match the current schema")
        if len(self.values) != len(FEATURE_NAMES):
            raise FeatureSchemaError("feature vector length does not match the current schema")
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in self.values):
            raise FeatureSchemaError("feature vector contains a non-numeric value")
        if not all(math.isfinite(value) for value in self.values):
            raise FeatureSchemaError("feature vector contains a non-finite value")
        if any(value < 0 for value in self.values):
            raise FeatureSchemaError("feature vector contains a negative value")
        feature_values = dict(zip(self.feature_names, self.values, strict=True))
        integer_names = (
            "total_packets",
            "total_bytes",
            "forward_packets",
            "reverse_packets",
            "forward_bytes",
            "reverse_bytes",
            "min_packet_size",
            "max_packet_size",
            "endpoint_a_port",
            "endpoint_b_port",
            "tcp_syn_count",
            "tcp_ack_count",
            "tcp_fin_count",
            "tcp_rst_count",
            "tcp_psh_count",
            "forward_packet_size_min",
            "forward_packet_size_max",
            "reverse_packet_size_min",
            "reverse_packet_size_max",
        )
        if any(feature_values[name] != int(feature_values[name]) for name in integer_names):
            raise FeatureSchemaError("count, size, and port features must be integer-valued")
        for name in ("endpoint_a_port", "endpoint_b_port"):
            if feature_values[name] > 65535:
                raise FeatureSchemaError(f"{name} is outside the valid port range")
        binary_names = (
            "protocol_tcp",
            "protocol_udp",
            "protocol_icmp",
            "protocol_icmpv6",
            "protocol_other",
            "endpoint_a_port_missing",
            "endpoint_b_port_missing",
            "forward_packet_size_missing",
            "reverse_packet_size_missing",
        )
        if any(feature_values[name] not in (0, 1) for name in binary_names):
            raise FeatureSchemaError("binary schema features must be 0 or 1")
        protocol_names = ("protocol_tcp", "protocol_udp", "protocol_icmp", "protocol_icmpv6", "protocol_other")
        if sum(feature_values[name] for name in protocol_names) != 1:
            raise FeatureSchemaError("exactly one protocol feature must be set")
        if feature_values["total_packets"] != feature_values["forward_packets"] + feature_values["reverse_packets"]:
            raise FeatureSchemaError("total_packets must equal the directional packet counts")
        if feature_values["total_bytes"] != feature_values["forward_bytes"] + feature_values["reverse_bytes"]:
            raise FeatureSchemaError("total_bytes must equal the directional byte counts")

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.feature_names, self.values, strict=True))

    def as_list(self) -> list[float]:
        return list(self.values)


def validate_model_schema(schema_version: str, feature_names: Sequence[str]) -> None:
    """Reject artifacts whose schema version or exact input order differs."""

    if schema_version != FEATURE_SCHEMA_VERSION:
        raise FeatureSchemaError(
            f"model feature schema {schema_version!r} does not match {FEATURE_SCHEMA_VERSION!r}"
        )
    if tuple(feature_names) != FEATURE_NAMES:
        raise FeatureSchemaError("model feature names or ordering do not match the current schema")


def extract_features(flow: FlowRecord) -> FeatureVector:
    """Return the finite numeric model input for one finalized flow."""

    total_packets = flow.total_packets
    total_bytes = flow.total_bytes
    duration = flow.duration_seconds
    packet_size_min = flow.packet_size_min
    packet_size_max = flow.packet_size_max
    protocol_name = flow.protocol.lower()

    raw: dict[str, float] = {
        "flow_duration_seconds": duration,
        "total_packets": float(total_packets),
        "total_bytes": float(total_bytes),
        "forward_packets": float(flow.forward.packet_count),
        "reverse_packets": float(flow.reverse.packet_count),
        "forward_bytes": float(flow.forward.byte_count),
        "reverse_bytes": float(flow.reverse.byte_count),
        "packets_per_second": total_packets / duration if duration > 0 else 0.0,
        "bytes_per_second": total_bytes / duration if duration > 0 else 0.0,
        "average_packet_size": total_bytes / total_packets if total_packets > 0 else 0.0,
        "min_packet_size": float(packet_size_min or 0),
        "max_packet_size": float(packet_size_max or 0),
        "protocol_tcp": float(protocol_name == "tcp"),
        "protocol_udp": float(protocol_name == "udp"),
        "protocol_icmp": float(protocol_name == "icmp"),
        "protocol_icmpv6": float(protocol_name == "icmpv6"),
        "protocol_other": float(protocol_name == "other"),
        "endpoint_a_port": float(flow.endpoint_a.port or 0),
        "endpoint_a_port_missing": float(flow.endpoint_a.port is None),
        "endpoint_b_port": float(flow.endpoint_b.port or 0),
        "endpoint_b_port_missing": float(flow.endpoint_b.port is None),
        "tcp_syn_count": float(flow.tcp_syn_count),
        "tcp_ack_count": float(flow.tcp_ack_count),
        "tcp_fin_count": float(flow.tcp_fin_count),
        "tcp_rst_count": float(flow.tcp_rst_count),
        "tcp_psh_count": float(flow.tcp_psh_count),
        "forward_packet_size_min": float(flow.forward.packet_size_min or 0),
        "forward_packet_size_max": float(flow.forward.packet_size_max or 0),
        "forward_packet_size_missing": float(flow.forward.packet_count == 0),
        "reverse_packet_size_min": float(flow.reverse.packet_size_min or 0),
        "reverse_packet_size_max": float(flow.reverse.packet_size_max or 0),
        "reverse_packet_size_missing": float(flow.reverse.packet_count == 0),
    }
    return FeatureVector(
        schema_version=FEATURE_SCHEMA_VERSION,
        feature_names=FEATURE_NAMES,
        values=tuple(raw[name] for name in FEATURE_NAMES),
    )
