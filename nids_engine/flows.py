"""Deterministic bidirectional flow aggregation for parsed packet metadata."""

from __future__ import annotations

import heapq
import ipaddress
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from nids_engine.packet import PacketMetadata, ProtocolName


class FinalizationReason(StrEnum):
    IDLE_TIMEOUT = "idle_timeout"
    ACTIVE_TIMEOUT = "active_timeout"
    CAPACITY = "capacity"
    END_OF_CAPTURE = "end_of_capture"


@dataclass(frozen=True, slots=True)
class Endpoint:
    ip: str | None
    port: int | None


@dataclass(frozen=True, slots=True)
class DirectionStats:
    packet_count: int
    byte_count: int
    packet_size_min: int | None
    packet_size_max: int | None
    tcp_syn_count: int = 0
    tcp_ack_count: int = 0
    tcp_fin_count: int = 0
    tcp_rst_count: int = 0
    tcp_psh_count: int = 0


@dataclass(frozen=True, slots=True)
class FlowRecord:
    """Finalized flow. Forward means endpoint A to endpoint B."""

    flow_id: str
    protocol: ProtocolName
    endpoint_a: Endpoint
    endpoint_b: Endpoint
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime
    forward: DirectionStats
    reverse: DirectionStats
    finalization_reason: FinalizationReason

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.last_seen_at - self.started_at).total_seconds())

    @property
    def total_packets(self) -> int:
        return self.forward.packet_count + self.reverse.packet_count

    @property
    def total_bytes(self) -> int:
        return self.forward.byte_count + self.reverse.byte_count

    @property
    def packet_size_min(self) -> int | None:
        values = [
            value
            for value in (self.forward.packet_size_min, self.reverse.packet_size_min)
            if value is not None
        ]
        return min(values) if values else None

    @property
    def packet_size_max(self) -> int | None:
        values = [
            value
            for value in (self.forward.packet_size_max, self.reverse.packet_size_max)
            if value is not None
        ]
        return max(values) if values else None

    @property
    def tcp_syn_count(self) -> int:
        return self.forward.tcp_syn_count + self.reverse.tcp_syn_count

    @property
    def tcp_ack_count(self) -> int:
        return self.forward.tcp_ack_count + self.reverse.tcp_ack_count

    @property
    def tcp_fin_count(self) -> int:
        return self.forward.tcp_fin_count + self.reverse.tcp_fin_count

    @property
    def tcp_rst_count(self) -> int:
        return self.forward.tcp_rst_count + self.reverse.tcp_rst_count

    @property
    def tcp_psh_count(self) -> int:
        return self.forward.tcp_psh_count + self.reverse.tcp_psh_count


@dataclass(frozen=True, slots=True)
class _FlowKey:
    protocol: ProtocolName
    endpoint_a: Endpoint
    endpoint_b: Endpoint
    unique_tag: int | None = None


@dataclass(slots=True)
class _MutableDirection:
    packet_count: int = 0
    byte_count: int = 0
    packet_size_min: int | None = None
    packet_size_max: int | None = None
    tcp_syn_count: int = 0
    tcp_ack_count: int = 0
    tcp_fin_count: int = 0
    tcp_rst_count: int = 0
    tcp_psh_count: int = 0

    def add(self, packet: PacketMetadata) -> None:
        self.packet_count += 1
        self.byte_count += packet.packet_length
        if self.packet_size_min is None or packet.packet_length < self.packet_size_min:
            self.packet_size_min = packet.packet_length
        if self.packet_size_max is None or packet.packet_length > self.packet_size_max:
            self.packet_size_max = packet.packet_length
        if packet.protocol != "TCP" or packet.tcp_flags is None:
            return
        flags = packet.tcp_flags
        self.tcp_fin_count += bool(flags & 0x01)
        self.tcp_syn_count += bool(flags & 0x02)
        self.tcp_rst_count += bool(flags & 0x04)
        self.tcp_psh_count += bool(flags & 0x08)
        self.tcp_ack_count += bool(flags & 0x10)

    def snapshot(self) -> DirectionStats:
        return DirectionStats(
            packet_count=self.packet_count,
            byte_count=self.byte_count,
            packet_size_min=self.packet_size_min,
            packet_size_max=self.packet_size_max,
            tcp_syn_count=self.tcp_syn_count,
            tcp_ack_count=self.tcp_ack_count,
            tcp_fin_count=self.tcp_fin_count,
            tcp_rst_count=self.tcp_rst_count,
            tcp_psh_count=self.tcp_psh_count,
        )


@dataclass(slots=True)
class _ActiveFlow:
    sequence: int
    key: _FlowKey
    started_at: datetime
    last_seen_at: datetime
    forward: _MutableDirection
    reverse: _MutableDirection


def _normalize_ip(address: str | None) -> str | None:
    if address is None:
        return None
    try:
        return ipaddress.ip_address(address).compressed.lower()
    except ValueError as exc:
        raise ValueError(f"invalid IP address in packet metadata: {address!r}") from exc


def _endpoint_order(endpoint: Endpoint) -> tuple[int, int | str, int]:
    if endpoint.ip is None:
        return (3, "", -1 if endpoint.port is None else endpoint.port)
    parsed = ipaddress.ip_address(endpoint.ip)
    return (parsed.version, int(parsed), -1 if endpoint.port is None else endpoint.port)


class FlowBuilder:
    """Group packets into bounded, timeout-based bidirectional flows.

    Expiration uses a monotonic event-time watermark. Out-of-order packet timestamps
    can move a flow's start earlier, but never move the watermark backwards.
    Packets without both IP endpoints become single-packet flows because their
    network identity is not available for a safe bidirectional key.
    """

    def __init__(
        self,
        *,
        idle_timeout_seconds: float = 60.0,
        active_timeout_seconds: float = 300.0,
        max_active_flows: int = 100_000,
    ) -> None:
        if not math.isfinite(idle_timeout_seconds) or idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive")
        if not math.isfinite(active_timeout_seconds) or active_timeout_seconds <= 0:
            raise ValueError("active_timeout_seconds must be positive")
        if max_active_flows <= 0:
            raise ValueError("max_active_flows must be positive")
        self.idle_timeout = timedelta(seconds=idle_timeout_seconds)
        self.active_timeout = timedelta(seconds=active_timeout_seconds)
        self.max_active_flows = max_active_flows
        self._watermark: datetime | None = None
        self._next_sequence = 1
        self._next_unkeyed_tag = 1
        self._active_by_key: dict[_FlowKey, _ActiveFlow] = {}
        self._active_by_sequence: dict[int, _ActiveFlow] = {}
        self._expiry_heap: list[tuple[datetime, int, int, str]] = []

    @property
    def active_count(self) -> int:
        return len(self._active_by_key)

    @property
    def watermark(self) -> datetime | None:
        return self._watermark

    def process(self, packet: PacketMetadata) -> list[FlowRecord]:
        """Add one packet and return flows finalized before it was added."""

        timestamp = packet.timestamp.astimezone(UTC)
        if self._watermark is None or timestamp > self._watermark:
            self._watermark = timestamp
        finalized = self._expire(self._watermark)

        key, is_forward = self._flow_key(packet)
        active = self._active_by_key.get(key)
        if active is None:
            if len(self._active_by_key) >= self.max_active_flows:
                oldest = min(
                    self._active_by_key.values(),
                    key=lambda item: (item.last_seen_at, item.sequence),
                )
                finalized.append(self._finalize(oldest, self._watermark, FinalizationReason.CAPACITY))
            active = self._new_flow(key, timestamp)

        previous_start = active.started_at
        previous_last_seen = active.last_seen_at
        if timestamp < active.started_at:
            active.started_at = timestamp
        if timestamp > active.last_seen_at:
            active.last_seen_at = timestamp
        (active.forward if is_forward else active.reverse).add(packet)

        if active.started_at != previous_start:
            self._schedule(active, "active")
        if active.last_seen_at != previous_last_seen:
            self._schedule(active, "idle")
        finalized.extend(self._expire(self._watermark))
        return finalized

    def flush(self) -> list[FlowRecord]:
        """Finalize remaining flows at end of input in deterministic order."""

        if self._watermark is None:
            return []
        records = [
            self._finalize(flow, self._watermark, FinalizationReason.END_OF_CAPTURE)
            for flow in sorted(self._active_by_sequence.values(), key=lambda item: item.sequence)
        ]
        self._expiry_heap.clear()
        return records

    def _flow_key(self, packet: PacketMetadata) -> tuple[_FlowKey, bool]:
        source = Endpoint(_normalize_ip(packet.src_ip), packet.src_port)
        destination = Endpoint(_normalize_ip(packet.dst_ip), packet.dst_port)
        is_forward = _endpoint_order(source) <= _endpoint_order(destination)
        endpoint_a, endpoint_b = (source, destination) if is_forward else (destination, source)
        unique_tag = None
        if source.ip is None or destination.ip is None:
            unique_tag = self._next_unkeyed_tag
            self._next_unkeyed_tag += 1
        return _FlowKey(packet.protocol, endpoint_a, endpoint_b, unique_tag), is_forward

    def _new_flow(self, key: _FlowKey, timestamp: datetime) -> _ActiveFlow:
        active = _ActiveFlow(
            sequence=self._next_sequence,
            key=key,
            started_at=timestamp,
            last_seen_at=timestamp,
            forward=_MutableDirection(),
            reverse=_MutableDirection(),
        )
        self._next_sequence += 1
        self._active_by_key[key] = active
        self._active_by_sequence[active.sequence] = active
        self._schedule(active, "idle")
        self._schedule(active, "active")
        return active

    def _schedule(self, flow: _ActiveFlow, kind: str) -> None:
        if kind == "idle":
            deadline = flow.last_seen_at + self.idle_timeout
            priority = 0
        else:
            deadline = flow.started_at + self.active_timeout
            priority = 1
        heapq.heappush(self._expiry_heap, (deadline, priority, flow.sequence, kind))
        self._compact_expirations_if_needed()

    def _expire(self, watermark: datetime) -> list[FlowRecord]:
        finalized: list[FlowRecord] = []
        while self._expiry_heap and self._expiry_heap[0][0] <= watermark:
            deadline, _priority, sequence, kind = heapq.heappop(self._expiry_heap)
            flow = self._active_by_sequence.get(sequence)
            if flow is None:
                continue
            if kind == "idle":
                expected_deadline = flow.last_seen_at + self.idle_timeout
                reason = FinalizationReason.IDLE_TIMEOUT
            else:
                expected_deadline = flow.started_at + self.active_timeout
                reason = FinalizationReason.ACTIVE_TIMEOUT
            if deadline != expected_deadline or expected_deadline > watermark:
                continue
            finalized.append(self._finalize(flow, watermark, reason))
        self._compact_expirations_if_needed()
        return finalized

    def _compact_expirations_if_needed(self) -> None:
        # Lazy invalidation keeps updates cheap; periodic rebuilding bounds stale entries.
        if len(self._expiry_heap) <= max(64, self.active_count * 4):
            return
        self._expiry_heap = []
        for flow in self._active_by_sequence.values():
            self._expiry_heap.append((flow.last_seen_at + self.idle_timeout, 0, flow.sequence, "idle"))
            self._expiry_heap.append((flow.started_at + self.active_timeout, 1, flow.sequence, "active"))
        heapq.heapify(self._expiry_heap)

    def _finalize(
        self,
        flow: _ActiveFlow,
        ended_at: datetime,
        reason: FinalizationReason,
    ) -> FlowRecord:
        self._active_by_key.pop(flow.key, None)
        self._active_by_sequence.pop(flow.sequence, None)
        return FlowRecord(
            flow_id=f"flow-{flow.sequence:010d}",
            protocol=flow.key.protocol,
            endpoint_a=flow.key.endpoint_a,
            endpoint_b=flow.key.endpoint_b,
            started_at=flow.started_at,
            last_seen_at=flow.last_seen_at,
            ended_at=max(ended_at, flow.last_seen_at),
            forward=flow.forward.snapshot(),
            reverse=flow.reverse.snapshot(),
            finalization_reason=reason,
        )
