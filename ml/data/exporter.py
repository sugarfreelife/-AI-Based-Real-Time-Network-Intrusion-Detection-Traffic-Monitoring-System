"""Convert project flow records to feature rows without inventing labels."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, Sequence

from nids_engine.capture import CaptureStats, replay_pcap
from nids_engine.features import FEATURE_NAMES, extract_features
from nids_engine.flows import FlowBuilder, FlowRecord
from nids_engine.packet import PacketMetadata


class LabelMappingError(ValueError):
    """Raised when human/ground-truth labels do not cover exactly the extracted flows."""


def extract_flows(pcap_path: str | Path) -> tuple[list[FlowRecord], CaptureStats]:
    builder = FlowBuilder()
    finalized: list[FlowRecord] = []

    def on_packet(metadata: PacketMetadata) -> None:
        finalized.extend(builder.process(metadata))

    stats = replay_pcap(pcap_path, on_packet)
    finalized.extend(builder.flush())
    return finalized, stats


def write_label_template(flows: Sequence[FlowRecord], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(("flow_id", "label"))
        writer.writerows((flow.flow_id, "") for flow in flows)
    return destination


def export_labeled_features(
    flows: Sequence[FlowRecord],
    labels: Mapping[str, str],
    capture_group: str,
    output_path: str | Path,
) -> Path:
    if not capture_group.strip():
        raise ValueError("capture_group cannot be empty")
    flow_ids = {flow.flow_id for flow in flows}
    label_ids = set(labels)
    missing = sorted(flow_ids - label_ids)
    unknown = sorted(label_ids - flow_ids)
    if missing or unknown:
        raise LabelMappingError(f"labels must cover exactly the extracted flows; missing={missing}, unknown={unknown}")
    if any(not label.strip() for label in labels.values()):
        raise LabelMappingError("all flow labels must be non-empty ground-truth values")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    columns = [*FEATURE_NAMES, "label", "capture_group"]
    with destination.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for flow in flows:
            row = extract_features(flow).as_dict()
            row["label"] = labels[flow.flow_id].strip()
            row["capture_group"] = capture_group.strip()
            writer.writerow(row)
    return destination
