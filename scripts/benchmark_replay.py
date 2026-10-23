"""Measure offline monitor CLI time on a generated synthetic fixture only."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from scripts.synthetic_demo import write_capture

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _summary(stderr: str) -> dict[str, object]:
    for line in reversed(stderr.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("monitor_summary"), dict):
            return value["monitor_summary"]
    raise ValueError("monitor did not emit its completion summary")


def benchmark(*, flows: int, syn_per_flow: int, runs: int, threshold: int) -> dict[str, object]:
    expected_packets = flows * syn_per_flow
    if expected_packets > 250_000:
        raise ValueError("benchmark fixture is limited to 250000 packets")
    elapsed_samples: list[float] = []
    flow_counts: list[int] = []
    alert_counts: list[int] = []

    with tempfile.TemporaryDirectory(prefix="nids-synthetic-benchmark-") as temp_directory:
        capture = Path(temp_directory) / "synthetic-benchmark-not-real-network.pcap"
        write_capture(capture, flows=flows, syn_per_flow=syn_per_flow)
        for _ in range(runs):
            started = time.perf_counter()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nids_engine.monitor",
                    "--pcap",
                    str(capture),
                    "--syn-burst-threshold",
                    str(threshold),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            elapsed = time.perf_counter() - started
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"monitor exited with {result.returncode}")
            summary = _summary(result.stderr)
            capture_summary = summary.get("capture")
            if not isinstance(capture_summary, dict) or capture_summary.get("packets_seen") != expected_packets:
                raise RuntimeError("monitor packet count did not match the synthetic fixture")
            elapsed_samples.append(elapsed)
            flow_counts.append(int(summary["flows"]))
            alert_counts.append(int(summary["alerts"]))

    median_seconds = statistics.median(elapsed_samples)
    rates = [expected_packets / seconds for seconds in elapsed_samples]
    per_packet_ms = [seconds * 1000 / expected_packets for seconds in elapsed_samples]
    return {
        "label": "SYNTHETIC SOFTWARE BENCHMARK — NOT REAL TRAFFIC OR MODEL PERFORMANCE",
        "workload": "offline monitor CLI; no database, model, or live network",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "flows_requested": flows,
        "syn_packets_per_flow": syn_per_flow,
        "input_packets_per_run": expected_packets,
        "runs": runs,
        "flow_count_per_run": flow_counts[0],
        "rule_alert_count_per_run": alert_counts[0],
        "median_end_to_end_seconds": round(median_seconds, 6),
        "median_packets_per_second": round(statistics.median(rates), 2),
        "median_end_to_end_ms_per_input_packet": round(statistics.median(per_packet_ms), 4),
        "sample_seconds_min": round(min(elapsed_samples), 6),
        "sample_seconds_max": round(max(elapsed_samples), 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flows", type=_positive_int, default=100)
    parser.add_argument("--syn-per-flow", type=_positive_int, default=24)
    parser.add_argument("--runs", type=_positive_int, default=5)
    parser.add_argument("--syn-burst-threshold", type=_positive_int, default=20)
    args = parser.parse_args(argv)
    try:
        report = benchmark(
            flows=args.flows,
            syn_per_flow=args.syn_per_flow,
            runs=args.runs,
            threshold=args.syn_burst_threshold,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
