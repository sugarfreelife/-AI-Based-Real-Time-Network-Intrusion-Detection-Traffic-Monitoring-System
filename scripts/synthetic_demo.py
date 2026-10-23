"""Generate an explicitly synthetic SYN-burst PCAP for local software demos."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scapy.layers.inet import IP, TCP
from scapy.utils import wrpcap

DEFAULT_OUTPUT = Path("pcaps/synthetic-demo-not-real-network.pcap")
DEFAULT_START = datetime(2026, 1, 1, tzinfo=UTC).timestamp()


def build_packets(*, flows: int = 8, syn_per_flow: int = 24):
    if not 1 <= flows <= 1_000:
        raise ValueError("flows must be between 1 and 1000")
    if not 20 <= syn_per_flow <= 1_000:
        raise ValueError("syn_per_flow must be between 20 and 1000 to trigger the default SYN rule")
    packets = []
    for flow_index in range(flows):
        start = DEFAULT_START + flow_index * 3
        for packet_index in range(syn_per_flow):
            packet = IP(src="203.0.113.10", dst="192.0.2.10") / TCP(
                sport=40_000 + flow_index,
                dport=443,
                flags="S",
                seq=flow_index * syn_per_flow + packet_index,
            )
            packet.time = start + packet_index * 0.05
            packets.append(packet)
    return packets


def write_capture(path: Path, *, flows: int = 8, syn_per_flow: int = 24, force: bool = False) -> int:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to replace the generated fixture")
    packets = build_packets(flows=flows, syn_per_flow=syn_per_flow)
    path.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(path), packets)
    return len(packets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--flows", type=int, default=8)
    parser.add_argument("--syn-per-flow", type=int, default=24)
    parser.add_argument("--force", action="store_true", help="replace the generated output file")
    args = parser.parse_args(argv)
    try:
        packets = write_capture(args.output, flows=args.flows, syn_per_flow=args.syn_per_flow, force=args.force)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "status": "generated",
        "label": "SYNTHETIC FIXTURE — NOT REAL NETWORK TRAFFIC",
        "path": str(args.output),
        "synthetic_flows": args.flows,
        "syn_packets_per_flow": args.syn_per_flow,
        "packets": packets,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
