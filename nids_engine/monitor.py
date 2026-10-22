"""Run the offline packet-to-flow-to-prediction-and-alert pipeline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from nids_engine.capture import CaptureError, replay_pcap
from nids_engine.detection import AlertEngine
from nids_engine.features import extract_features
from nids_engine.flows import FlowBuilder, FlowRecord
from nids_engine.inference import InferenceEngine
from nids_engine.packet import PacketMetadata


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _positive_finite(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive finite number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive finite number")
    return parsed


def _flow_dict(flow: FlowRecord) -> dict[str, Any]:
    return {
        "flow_id": flow.flow_id,
        "protocol": flow.protocol,
        "endpoint_a": {"ip": flow.endpoint_a.ip, "port": flow.endpoint_a.port},
        "endpoint_b": {"ip": flow.endpoint_b.ip, "port": flow.endpoint_b.port},
        "started_at": flow.started_at.isoformat(),
        "last_seen_at": flow.last_seen_at.isoformat(),
        "ended_at": flow.ended_at.isoformat(),
        "finalization_reason": flow.finalization_reason.value,
        "features": extract_features(flow).as_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay an authorized PCAP through flow aggregation, optional ML inference, and explainable alerts."
    )
    parser.add_argument("--pcap", required=True, help="authorized offline PCAP/PCAPNG input")
    parser.add_argument("--model", help="trusted project .joblib model; omit for rule-only mode")
    parser.add_argument(
        "--benign-label", action="append", default=None,
        help="model class treated as benign; repeat for multiple classes (default: BENIGN)",
    )
    parser.add_argument("--syn-burst-threshold", type=_positive_int, default=20)
    parser.add_argument("--high-packets-per-second", type=_positive_finite, default=1000.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inference = InferenceEngine.from_path(args.model)
    alerts = AlertEngine(
        benign_labels=tuple(args.benign_label or ("BENIGN",)),
        syn_burst_threshold=args.syn_burst_threshold,
        high_packet_rate_threshold=args.high_packets_per_second,
    )
    builder = FlowBuilder()
    counts = {"flows": 0, "scored": 0, "unscored": 0, "alerts": 0}
    prediction_status_counts: dict[str, int] = {}

    def emit_flow(flow: FlowRecord) -> None:
        prediction = inference.predict(flow)
        flow_alerts = alerts.evaluate(flow, prediction)
        counts["flows"] += 1
        counts["scored"] += prediction.status == "scored"
        counts["unscored"] += prediction.status != "scored"
        counts["alerts"] += len(flow_alerts)
        prediction_status_counts[prediction.status] = prediction_status_counts.get(prediction.status, 0) + 1
        print(json.dumps({
            "flow": _flow_dict(flow),
            "prediction": prediction.as_dict(),
            "alerts": [alert.as_dict() for alert in flow_alerts],
        }, separators=(",", ":")))

    def on_packet(metadata: PacketMetadata) -> None:
        for flow in builder.process(metadata):
            emit_flow(flow)

    try:
        stats = replay_pcap(args.pcap, on_packet)
        for flow in builder.flush():
            emit_flow(flow)
    except (CaptureError, OSError, ValueError) as exc:
        print(json.dumps({"monitor_error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps({
        "monitor_summary": {
            **counts,
            "prediction_status_counts": prediction_status_counts,
            "suppressed_duplicate_alerts": alerts.suppressed_count,
            "model_status": inference.status,
            "model_version": inference.model_version,
            "capture": stats.as_dict(),
        }
    }, separators=(",", ":")), file=sys.stderr)
    return 0 if stats.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
