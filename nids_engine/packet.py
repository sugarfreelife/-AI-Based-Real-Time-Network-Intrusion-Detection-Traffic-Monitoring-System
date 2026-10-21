"""Parse Scapy packets into stable metadata records without retaining payloads."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6

ProtocolName = Literal["TCP", "UDP", "ICMP", "ICMPV6", "OTHER"]


class PacketParseError(ValueError):
    """Raised when a packet cannot be converted to valid metadata."""


@dataclass(frozen=True, slots=True)
class PacketMetadata:
    """Transport and network metadata needed downstream; packet payload is omitted."""

    timestamp: datetime
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    protocol: ProtocolName
    packet_length: int
    ip_version: int | None
    tcp_flags: int | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.packet_length < 0:
            raise ValueError("packet_length cannot be negative")
        for field_name in ("src_port", "dst_port"):
            port = getattr(self, field_name)
            if port is not None and not 0 <= port <= 65535:
                raise ValueError(f"{field_name} must be between 0 and 65535")


def _packet_timestamp(packet: object) -> datetime:
    try:
        timestamp_seconds = float(getattr(packet, "time"))
        if not math.isfinite(timestamp_seconds):
            raise ValueError("timestamp is not finite")
        return datetime.fromtimestamp(timestamp_seconds, tz=UTC)
    except (AttributeError, TypeError, ValueError, OverflowError, OSError) as exc:
        raise PacketParseError("packet has an invalid capture timestamp") from exc


def parse_packet(packet: object) -> PacketMetadata:
    """Extract a bounded metadata record from a Scapy packet.

    Unknown or non-IP packets are retained as ``OTHER`` with absent network fields.
    Raw payload bytes are never returned or stored in ``PacketMetadata``.
    """

    try:
        timestamp = _packet_timestamp(packet)
        packet_length = len(packet)  # type: ignore[arg-type]

        ip_layer = packet.getlayer(IP)  # type: ignore[attr-defined]
        ipv6_layer = packet.getlayer(IPv6)  # type: ignore[attr-defined]
        network_layer = ip_layer if ip_layer is not None else ipv6_layer
        ip_version = 4 if ip_layer is not None else 6 if ipv6_layer is not None else None
        src_ip = str(network_layer.src) if network_layer is not None else None
        dst_ip = str(network_layer.dst) if network_layer is not None else None

        tcp_layer = packet.getlayer(TCP)  # type: ignore[attr-defined]
        udp_layer = packet.getlayer(UDP)  # type: ignore[attr-defined]
        tcp_flags: int | None = None
        src_port: int | None = None
        dst_port: int | None = None

        if tcp_layer is not None:
            protocol: ProtocolName = "TCP"
            src_port = int(tcp_layer.sport)
            dst_port = int(tcp_layer.dport)
            tcp_flags = int(tcp_layer.flags)
        elif udp_layer is not None:
            protocol = "UDP"
            src_port = int(udp_layer.sport)
            dst_port = int(udp_layer.dport)
        elif ip_layer is not None and int(ip_layer.proto) == 1:
            protocol = "ICMP"
        elif ipv6_layer is not None and int(ipv6_layer.nh) == 58:
            protocol = "ICMPV6"
        elif packet.haslayer(ICMP):  # type: ignore[attr-defined]
            protocol = "ICMP"
        elif ip_version == 6 and int(ipv6_layer.nh) == 58:
            protocol = "ICMPV6"
        else:
            protocol = "OTHER"

        return PacketMetadata(
            timestamp=timestamp,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            packet_length=packet_length,
            ip_version=ip_version,
            tcp_flags=tcp_flags,
        )
    except PacketParseError:
        raise
    except Exception as exc:
        raise PacketParseError("packet metadata could not be parsed") from exc
