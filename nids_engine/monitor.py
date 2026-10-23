"""Run the offline packet-to-flow-to-prediction-and-alert pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nids_engine.capture import CaptureError, replay_pcap
from nids_engine.detection import AlertEngine
from nids_engine.features import extract_features
from nids_engine.flows import FlowBuilder, FlowRecord
from nids_engine.inference import InferenceEngine
from nids_engine.packet import PacketMetadata


class PersistenceError(RuntimeError):
    """A configured database write failed; replay must stop to avoid silent loss."""


logger = logging.getLogger("nids_engine.monitor")


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


def _failure_code(error: Exception) -> str:
    if isinstance(error, PersistenceError):
        return "persistence_error"
    if isinstance(error, CaptureError):
        return "capture_error"
    if isinstance(error, OSError):
        return "file_error"
    return "replay_error"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay an authorized PCAP through flow aggregation, optional ML inference, and explainable alerts."
    )
    parser.add_argument("--pcap", required=True, help="authorized offline PCAP/PCAPNG input")
    parser.add_argument("--model", help="trusted project .joblib model; omit for rule-only mode")
    parser.add_argument("--database-url", help="persist each completed flow/prediction/alert transaction to this database")
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
    capture_id = str(uuid4())
    capture_started_at = datetime.now(UTC)
    source_name = Path(args.pcap).name[:255] or "capture"
    session_factory = None
    database_engine = None
    if args.database_url:
        try:
            from sqlalchemy.exc import SQLAlchemyError
            from sqlalchemy.orm import sessionmaker

            from backend.app.database.session import make_engine
            from backend.app.database.models import CaptureRunDB
            from backend.app.services.ingestion import persist_observation

            database_engine = make_engine(args.database_url)
            session_factory = sessionmaker(bind=database_engine, autoflush=False, expire_on_commit=False)
            with session_factory.begin() as session:
                session.add(CaptureRunDB(
                    capture_id=capture_id,
                    source_name=source_name,
                    status="running",
                    started_at=capture_started_at,
                    model_status=str(inference.status),
                    model_version=inference.model_version,
                ))
        except Exception as exc:
            if database_engine is not None:
                database_engine.dispose()
            print(json.dumps({
                "monitor_error": "database write failed; capture run could not be recorded",
                "capture_id": capture_id,
                "completed_flows": 0,
                "failure_reason": _failure_code(exc),
            }), file=sys.stderr)
            return 1
    else:
        SQLAlchemyError = None
        persist_observation = None
    alerts = AlertEngine(
        benign_labels=tuple(args.benign_label or ("BENIGN",)),
        syn_burst_threshold=args.syn_burst_threshold,
        high_packet_rate_threshold=args.high_packets_per_second,
    )
    builder = FlowBuilder()
    counts = {"flows": 0, "scored": 0, "unscored": 0, "alerts": 0}
    prediction_status_counts: dict[str, int] = {}
    processed_packets = 0

    def update_capture_run(
        *,
        status_value: str,
        stats: Any | None = None,
        failure_reason: str | None = None,
    ) -> None:
        if session_factory is None:
            return
        from backend.app.database.models import CaptureRunDB

        try:
            with session_factory.begin() as session:
                run = session.get(CaptureRunDB, capture_id)
                if run is None:
                    raise PersistenceError("capture run record disappeared during replay")
                run.status = status_value
                run.completed_at = datetime.now(UTC)
                run.packets_seen = int(stats.packets_seen) if stats is not None else processed_packets
                run.packets_processed = int(stats.packets_processed) if stats is not None else processed_packets
                run.packets_filtered = int(stats.packets_filtered) if stats is not None else 0
                run.parsing_failures = int(stats.parsing_failures) if stats is not None else 0
                run.read_failures = int(stats.read_failures) if stats is not None else 0
                run.flow_count = int(counts["flows"])
                run.scored_count = int(counts["scored"])
                run.unscored_count = int(counts["unscored"])
                run.alert_count = int(counts["alerts"])
                run.suppressed_duplicate_alerts = alerts.suppressed_count
                run.elapsed_seconds = float(stats.elapsed_seconds) if stats is not None else None
                run.failure_reason = failure_reason
        except Exception as exc:
            raise PersistenceError("database write failed while recording capture run status") from exc

    def emit_flow(flow: FlowRecord) -> None:
        prediction = inference.predict(flow)
        flow_alerts = alerts.evaluate(flow, prediction)
        if session_factory is not None and persist_observation is not None:
            try:
                with session_factory() as session:
                    with session.begin():
                        persist_observation(
                            session,
                            capture_id=capture_id,
                            flow=flow,
                            prediction=prediction,
                            alerts=flow_alerts,
                        )
            except SQLAlchemyError as exc:
                raise PersistenceError("database write failed; replay stopped before this flow was reported") from exc
        counts["flows"] += 1
        counts["scored"] += prediction.status == "scored"
        counts["unscored"] += prediction.status != "scored"
        counts["alerts"] += len(flow_alerts)
        prediction_status_counts[prediction.status] = prediction_status_counts.get(prediction.status, 0) + 1
        print(json.dumps({
            "capture_id": capture_id,
            "flow": _flow_dict(flow),
            "prediction": prediction.as_dict(),
            "alerts": [alert.as_dict() for alert in flow_alerts],
        }, separators=(",", ":")))

    def on_packet(metadata: PacketMetadata) -> None:
        nonlocal processed_packets
        for flow in builder.process(metadata):
            emit_flow(flow)
        processed_packets += 1

    try:
        stats = replay_pcap(args.pcap, on_packet)
        for flow in builder.flush():
            emit_flow(flow)
        update_capture_run(status_value=stats.status, stats=stats)
    except (CaptureError, OSError, ValueError, PersistenceError) as exc:
        try:
            update_capture_run(status_value="failed", failure_reason=_failure_code(exc))
        except PersistenceError:
            logger.exception("capture_run_failure_status_write_failed", extra={"capture_id": capture_id})
        print(json.dumps({
            "monitor_error": str(exc),
            "capture_id": capture_id,
            "completed_flows": counts["flows"],
            "failure_reason": _failure_code(exc),
        }), file=sys.stderr)
        if database_engine is not None:
            database_engine.dispose()
        return 1

    print(json.dumps({
        "monitor_summary": {
            **counts,
            "prediction_status_counts": prediction_status_counts,
            "capture_id": capture_id,
            "persisted": session_factory is not None,
            "suppressed_duplicate_alerts": alerts.suppressed_count,
            "model_status": inference.status,
            "model_version": inference.model_version,
            "capture": stats.as_dict(),
        }
    }, separators=(",", ":")), file=sys.stderr)
    if database_engine is not None:
        database_engine.dispose()
    return 0 if stats.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
