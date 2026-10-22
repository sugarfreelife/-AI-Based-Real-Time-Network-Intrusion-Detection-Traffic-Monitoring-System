"""Create label templates or labeled feature CSVs from authorized PCAPs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ml.data.exporter import export_labeled_features, extract_flows, write_label_template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract project-schema flow features from an authorized offline PCAP."
    )
    parser.add_argument("--pcap", required=True)
    parser.add_argument("--capture-group", required=True, help="stable identifier for this independent capture")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--labels", help="CSV with flow_id,label ground-truth rows")
    action.add_argument("--write-label-template", help="write a blank flow_id,label template to this path")
    parser.add_argument("--output", help="labeled feature CSV destination; required with --labels")
    args = parser.parse_args(argv)

    if args.labels and not args.output:
        parser.error("--output is required with --labels")
    pcap_path = Path(args.pcap).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    template_path = Path(args.write_label_template).resolve() if args.write_label_template else None
    labels_path = Path(args.labels).resolve() if args.labels else None
    if output_path == pcap_path or template_path == pcap_path:
        parser.error("output path cannot overwrite the source PCAP")
    if output_path is not None and output_path == labels_path:
        parser.error("feature output path cannot overwrite the label CSV")
    flows, capture_stats = extract_flows(args.pcap)
    if capture_stats.status != "completed" or capture_stats.parsing_failures or capture_stats.read_failures:
        parser.error(
            "capture replay was incomplete: "
            f"status={capture_stats.status}, parsing_failures={capture_stats.parsing_failures}, "
            f"read_failures={capture_stats.read_failures}"
        )
    if args.write_label_template:
        template_path = write_label_template(flows, args.write_label_template)
        print(json.dumps({"flows": len(flows), "label_template": str(template_path)}, indent=2))
        return 0

    with Path(args.labels).open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["flow_id", "label"]:
            parser.error("label CSV header must be exactly: flow_id,label")
        labels: dict[str, str] = {}
        for row in reader:
            flow_id = (row.get("flow_id") or "").strip()
            label = (row.get("label") or "").strip()
            if not flow_id or not label:
                parser.error("each label row must contain a flow_id and a ground-truth label")
            if flow_id in labels:
                parser.error(f"duplicate flow_id in labels file: {flow_id}")
            labels[flow_id] = label

    output_path = export_labeled_features(flows, labels, args.capture_group, args.output)
    print(json.dumps({"flows": len(flows), "output": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
