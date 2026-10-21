"""Command-line entry point for safe offline replay and optional live capture."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime

from nids_engine.capture import CaptureError, capture_live, replay_pcap
from nids_engine.logging_config import configure_json_logging
from nids_engine.packet import PacketMetadata


def _emit_packet(metadata: PacketMetadata) -> None:
    row = asdict(metadata)
    row["timestamp"] = metadata.timestamp.isoformat()
    print(json.dumps(row, separators=(",", ":")))


def _protocol(value: str) -> str:
    normalized = value.strip().upper()
    allowed = {"TCP", "UDP", "ICMP", "ICMPV6", "OTHER"}
    if normalized not in allowed:
        raise argparse.ArgumentTypeError(f"choose one of: {', '.join(sorted(allowed))}")
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stream packet metadata from an authorized PCAP or selected interface.",
        epilog="Live capture requires authorization and host packet-capture support. Payloads are not stored.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pcap", type=str, help="offline PCAP/PCAPNG path (recommended)")
    source.add_argument("--live", metavar="INTERFACE", help="capture from this explicitly selected interface")
    parser.add_argument("--protocol", action="append", type=_protocol, help="protocol filter; may be repeated")
    parser.add_argument("--bpf-filter", help="optional BPF filter for live capture only")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_json_logging(getattr(logging, args.log_level))
    if args.bpf_filter and not args.live:
        print("--bpf-filter is only available with --live", file=sys.stderr)
        return 2

    try:
        if args.pcap:
            stats = replay_pcap(args.pcap, _emit_packet, protocols=args.protocol)
        else:
            stats = capture_live(
                args.live,
                _emit_packet,
                protocols=args.protocol,
                bpf_filter=args.bpf_filter,
            )
    except (CaptureError, OSError, ValueError) as exc:
        logging.getLogger("nids_engine.cli").error("capture_failed", extra={"error": str(exc)})
        return 1

    print(json.dumps({"capture_summary": stats.as_dict()}, separators=(",", ":")), file=sys.stderr)
    return 0 if stats.status in {"completed", "interrupted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
