"""Explainable model and threshold-based alert generation."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from nids_engine.features import extract_features
from nids_engine.flows import FlowRecord
from nids_engine.inference import PredictionResult


@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    flow_id: str
    detection_code: str
    source: str
    severity: str
    title: str
    explanation: str
    occurred_at_utc: str
    protocol: str
    endpoint_a: dict[str, Any]
    endpoint_b: dict[str, Any]
    model_version: str | None
    evidence: dict[str, Any]
    status: str = "new"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlertDeduplicator:
    """Suppress repeated signatures within a time window using bounded memory."""

    def __init__(self, *, window_seconds: float = 60.0, max_entries: int = 50_000) -> None:
        if window_seconds <= 0 or max_entries <= 0:
            raise ValueError("deduplication window and maximum entries must be positive")
        self.window_seconds = window_seconds
        self.max_entries = max_entries
        self._seen: OrderedDict[tuple[str, ...], float] = OrderedDict()

    def is_duplicate(self, signature: tuple[str, ...], occurred_at: datetime) -> bool:
        timestamp = occurred_at.astimezone(UTC).timestamp()
        previous = self._seen.get(signature)
        if previous is not None and abs(timestamp - previous) <= self.window_seconds:
            self._seen[signature] = max(previous, timestamp)
            self._seen.move_to_end(signature)
            return True
        self._seen[signature] = timestamp
        self._seen.move_to_end(signature)
        while len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)
        return False


class AlertEngine:
    """Apply configured benign labels and transparent per-flow heuristics."""

    def __init__(
        self,
        *,
        benign_labels: tuple[str, ...] = ("BENIGN",),
        syn_burst_threshold: int = 20,
        high_packet_rate_threshold: float = 1000.0,
        deduplicator: AlertDeduplicator | None = None,
    ) -> None:
        if not benign_labels or any(not label.strip() for label in benign_labels):
            raise ValueError("at least one non-empty benign label is required")
        if syn_burst_threshold <= 0 or high_packet_rate_threshold <= 0:
            raise ValueError("alert thresholds must be positive")
        self.benign_labels = frozenset(benign_labels)
        self.syn_burst_threshold = syn_burst_threshold
        self.high_packet_rate_threshold = high_packet_rate_threshold
        self.deduplicator = deduplicator or AlertDeduplicator()
        self.suppressed_count = 0

    def evaluate(self, flow: FlowRecord, prediction: PredictionResult) -> list[Alert]:
        candidates: list[tuple[str, str, str, str, str | None, dict[str, Any]]] = []
        if prediction.status == "scored" and prediction.predicted_label is not None:
            if prediction.predicted_label not in self.benign_labels:
                candidates.append((
                    f"ml_classification:{prediction.predicted_label}",
                    "machine_learning",
                    "high",
                    f"Model classified flow as {prediction.predicted_label}",
                    prediction.model_version,
                    {"predicted_label": prediction.predicted_label, "benign_labels": sorted(self.benign_labels)},
                ))

        if flow.protocol == "TCP" and flow.tcp_syn_count >= self.syn_burst_threshold and flow.tcp_ack_count == 0:
            candidates.append((
                "tcp_syn_burst",
                "rule",
                "medium",
                "Possible TCP SYN burst",
                None,
                {
                    "tcp_syn_count": flow.tcp_syn_count,
                    "tcp_ack_count": flow.tcp_ack_count,
                    "threshold": self.syn_burst_threshold,
                },
            ))

        features = extract_features(flow).as_dict()
        packet_rate = features["packets_per_second"]
        if packet_rate >= self.high_packet_rate_threshold:
            candidates.append((
                "high_packet_rate",
                "rule",
                "medium",
                "High packet rate for one flow",
                None,
                {"packets_per_second": packet_rate, "threshold": self.high_packet_rate_threshold},
            ))

        alerts: list[Alert] = []
        for code, source, severity, title, model_version, evidence in candidates:
            signature = (code, flow.protocol, str(flow.endpoint_a), str(flow.endpoint_b))
            if self.deduplicator.is_duplicate(signature, flow.started_at):
                self.suppressed_count += 1
                continue
            alerts.append(Alert(
                alert_id=str(uuid.uuid4()),
                flow_id=flow.flow_id,
                detection_code=code,
                source=source,
                severity=severity,
                title=title,
                explanation=(
                    "A trained classifier produced this class; validate against local ground truth."
                    if source == "machine_learning"
                    else "A transparent threshold rule matched; this heuristic is a review signal, not proof of compromise."
                ),
                occurred_at_utc=flow.ended_at.astimezone(UTC).isoformat(),
                protocol=flow.protocol,
                endpoint_a={"ip": flow.endpoint_a.ip, "port": flow.endpoint_a.port},
                endpoint_b={"ip": flow.endpoint_b.ip, "port": flow.endpoint_b.port},
                model_version=model_version,
                evidence=evidence,
            ))
        return alerts
