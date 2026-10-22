"""Provenance manifest for one project-schema CSV dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from nids_engine.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


class ManifestError(ValueError):
    """Raised when dataset provenance is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_name: str
    source_url: str
    citation: str
    prepared_csv_sha256: str
    feature_schema_version: str
    label_column: str
    capture_group_column: str
    created_at_utc: str
    upstream_sha256: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for name in ("dataset_name", "source_url", "citation", "label_column", "capture_group_column"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"{name} cannot be empty")
        if self.label_column == self.capture_group_column:
            raise ManifestError("label and capture-group columns must be different")
        if self.label_column in FEATURE_NAMES or self.capture_group_column in FEATURE_NAMES:
            raise ManifestError("label and capture-group columns must be separate from model features")
        if self.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ManifestError(
                f"manifest schema {self.feature_schema_version!r} does not match {FEATURE_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.prepared_csv_sha256, str) or len(self.prepared_csv_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.prepared_csv_sha256.lower()
        ):
            raise ManifestError("prepared_csv_sha256 must be a 64-character hexadecimal SHA-256")
        if not isinstance(self.created_at_utc, str):
            raise ManifestError("created_at_utc must be an ISO-8601 timestamp")
        try:
            timestamp = datetime.fromisoformat(self.created_at_utc)
        except ValueError as exc:
            raise ManifestError("created_at_utc must be an ISO-8601 timestamp") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ManifestError("created_at_utc must include a timezone")
        if not isinstance(self.upstream_sha256, dict):
            raise ManifestError("upstream_sha256 must be an object mapping artifact names to SHA-256 values")
        for artifact_name, digest in self.upstream_sha256.items():
            if not isinstance(artifact_name, str) or not isinstance(digest, str):
                raise ManifestError("upstream_sha256 entries must be strings")
            if not artifact_name.strip() or len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest.lower()
            ):
                raise ManifestError("upstream_sha256 entries must map artifact names to SHA-256 values")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_file(cls, path: str | Path) -> DatasetManifest:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            manifest = cls(**payload)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ManifestError(f"could not read dataset manifest: {path}") from exc
        manifest.validate()
        return manifest


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    csv_path: str | Path,
    *,
    dataset_name: str,
    source_url: str,
    citation: str,
    label_column: str = "label",
    capture_group_column: str = "capture_group",
    upstream_sha256: Mapping[str, str] | None = None,
) -> DatasetManifest:
    manifest = DatasetManifest(
        dataset_name=dataset_name.strip(),
        source_url=source_url.strip(),
        citation=citation.strip(),
        prepared_csv_sha256=sha256_file(csv_path),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        label_column=label_column.strip(),
        capture_group_column=capture_group_column.strip(),
        created_at_utc=datetime.now(UTC).isoformat(),
        upstream_sha256=dict(upstream_sha256 or {}),
    )
    manifest.validate()
    return manifest


def write_manifest(manifest: DatasetManifest, output_path: str | Path) -> Path:
    manifest.validate()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a feature CSV and write its provenance manifest.")
    parser.add_argument("--csv", required=True, help="project-schema feature CSV")
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--citation", required=True)
    parser.add_argument("--output", required=True, help="manifest JSON output path")
    parser.add_argument(
        "--upstream-checksum",
        action="append",
        default=[],
        metavar="NAME=SHA256",
        help="record a checksum for an original input artifact; may be repeated",
    )
    args = parser.parse_args(argv)

    if Path(args.csv).resolve() == Path(args.output).resolve():
        parser.error("manifest output path cannot overwrite the feature CSV")

    from ml.data.loader import load_feature_dataset

    upstream_sha256 = {}
    for entry in args.upstream_checksum:
        name, separator, digest = entry.partition("=")
        if not separator or not name.strip() or not digest.strip():
            parser.error("--upstream-checksum must use NAME=SHA256")
        upstream_sha256[name.strip()] = digest.strip().lower()
    manifest = build_manifest(
        args.csv,
        dataset_name=args.dataset_name,
        source_url=args.source_url,
        citation=args.citation,
        upstream_sha256=upstream_sha256,
    )
    bundle = load_feature_dataset(args.csv, manifest)
    write_manifest(manifest, args.output)
    print(
        json.dumps(
            {
                "manifest": str(args.output),
                "rows": bundle.summary.rows_after_deduplication,
                "duplicates_removed": bundle.summary.duplicates_removed,
                "capture_groups": bundle.summary.capture_group_count,
                "class_counts": bundle.summary.class_counts,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
