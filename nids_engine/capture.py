"""Streaming PCAP replay and optional interface capture."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

from nids_engine.packet import PacketMetadata, PacketParseError, parse_packet

logger = logging.getLogger("nids_engine.capture")
PacketHandler = Callable[[PacketMetadata], None]


class CaptureError(RuntimeError):
    """Raised when a capture source cannot be opened or started."""


@dataclass(slots=True)
class CaptureStats:
    """Counts and duration for one capture or replay run."""

    source: str
    status: str = "running"
    packets_seen: int = 0
    packets_processed: int = 0
    packets_filtered: int = 0
    parsing_failures: int = 0
    read_failures: int = 0
    started_at: datetime | None = None
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        if self.started_at is not None:
            result["started_at"] = self.started_at.isoformat()
        return result


def _normalize_protocols(protocols: Iterable[str] | None) -> frozenset[str] | None:
    if protocols is None:
        return None
    normalized = frozenset(protocol.strip().upper() for protocol in protocols)
    supported = {"TCP", "UDP", "ICMP", "ICMPV6", "OTHER"}
    invalid = normalized - supported
    if invalid:
        raise ValueError(f"unsupported protocol filter: {', '.join(sorted(invalid))}")
    return normalized


def _finish(stats: CaptureStats, started: float, *, status: str = "completed") -> None:
    stats.elapsed_seconds = max(0.0, time.perf_counter() - started)
    stats.status = status
    logger.info(
        "capture_finished",
        extra={
            "pcap_path": stats.source if not stats.source.startswith("interface:") else None,
            "interface": stats.source.removeprefix("interface:") if stats.source.startswith("interface:") else None,
            "packets_seen": stats.packets_seen,
            "packets_processed": stats.packets_processed,
            "packets_filtered": stats.packets_filtered,
            "parsing_failures": stats.parsing_failures,
            "read_failures": stats.read_failures,
            "elapsed_seconds": stats.elapsed_seconds,
            "status": stats.status,
        },
    )


def replay_pcap(
    pcap_path: str | Path,
    on_packet: PacketHandler,
    *,
    protocols: Iterable[str] | None = None,
) -> CaptureStats:
    """Read a PCAP incrementally and invoke ``on_packet`` for accepted metadata."""

    from scapy.utils import PcapReader

    path = Path(pcap_path)
    accepted_protocols = _normalize_protocols(protocols)
    started = time.perf_counter()
    stats = CaptureStats(source=str(path), started_at=datetime.now(UTC))

    try:
        reader = PcapReader(str(path))
    except Exception as exc:
        _finish(stats, started, status="failed")
        raise CaptureError(f"could not open PCAP file: {path}") from exc

    try:
        with reader:
            while True:
                try:
                    packet = reader.read_packet()
                except EOFError:
                    break
                except Exception:
                    stats.read_failures += 1
                    logger.exception("pcap_read_failed", extra={"pcap_path": str(path)})
                    stats.status = "partial"
                    break

                if packet is None:
                    break
                stats.packets_seen += 1
                try:
                    metadata = parse_packet(packet)
                except PacketParseError:
                    stats.parsing_failures += 1
                    logger.exception("packet_parse_failed", extra={"pcap_path": str(path)})
                    continue

                if accepted_protocols is not None and metadata.protocol not in accepted_protocols:
                    stats.packets_filtered += 1
                    continue
                on_packet(metadata)
                stats.packets_processed += 1
    except Exception:
        _finish(stats, started, status="failed")
        raise
    else:
        final_status = "completed" if stats.status == "running" else stats.status
        _finish(stats, started, status=final_status)
    return stats


def capture_live(
    interface: str,
    on_packet: PacketHandler,
    *,
    protocols: Iterable[str] | None = None,
    bpf_filter: str | None = None,
) -> CaptureStats:
    """Capture metadata from one explicitly selected, authorized interface.

    Live capture is optional and requires Scapy's host packet-capture support.
    The interface is never selected implicitly.
    """

    if not interface or not interface.strip():
        raise ValueError("an explicit network interface is required")
    from scapy.sendrecv import sniff

    accepted_protocols = _normalize_protocols(protocols)
    started = time.perf_counter()
    stats = CaptureStats(source=f"interface:{interface}", started_at=datetime.now(UTC))

    def handle_packet(packet: object) -> None:
        stats.packets_seen += 1
        try:
            metadata = parse_packet(packet)
        except PacketParseError:
            stats.parsing_failures += 1
            logger.exception("packet_parse_failed", extra={"interface": interface})
            return
        if accepted_protocols is not None and metadata.protocol not in accepted_protocols:
            stats.packets_filtered += 1
            return
        on_packet(metadata)
        stats.packets_processed += 1

    logger.info("live_capture_started", extra={"interface": interface})
    try:
        sniff(iface=interface, filter=bpf_filter, prn=handle_packet, store=False, verbose=0)
    except KeyboardInterrupt:
        _finish(stats, started, status="interrupted")
        return stats
    except Exception as exc:
        _finish(stats, started, status="failed")
        raise CaptureError(f"live capture failed on interface {interface!r}") from exc
    _finish(stats, started)
    return stats
