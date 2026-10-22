"""Combine per-capture labeled feature CSVs without changing their rows."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from nids_engine.features import FEATURE_NAMES

EXPECTED_COLUMNS = [*FEATURE_NAMES, "label", "capture_group"]


def combine_csvs(inputs: list[str | Path], output_path: str | Path) -> tuple[Path, int]:
    if not inputs:
        raise ValueError("at least one input CSV is required")
    destination = Path(output_path)
    resolved_destination = destination.resolve()
    resolved_inputs = [Path(input_path).resolve() for input_path in inputs]
    if resolved_destination in resolved_inputs:
        raise ValueError("output path cannot overwrite an input CSV")
    destination.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.",
            suffix=".tmp", delete=False,
        ) as output:
            temporary_path = Path(output.name)
            writer = csv.DictWriter(output, fieldnames=EXPECTED_COLUMNS)
            writer.writeheader()
            for input_path in inputs:
                with Path(input_path).open("r", newline="", encoding="utf-8-sig") as source:
                    reader = csv.DictReader(source)
                    if reader.fieldnames != EXPECTED_COLUMNS:
                        raise ValueError(f"unexpected feature CSV header in {input_path}")
                    for row in reader:
                        if not row.get("label", "").strip() or not row.get("capture_group", "").strip():
                            raise ValueError(f"missing label or capture_group in {input_path}")
                        writer.writerow(row)
                        row_count += 1
        temporary_path.replace(destination)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return destination, row_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Combine per-capture feature CSVs into one training table.")
    parser.add_argument("--input", action="append", required=True, help="input CSV; may be repeated")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output_path, row_count = combine_csvs(args.input, args.output)
    print(f"Wrote {row_count} labeled flow rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
