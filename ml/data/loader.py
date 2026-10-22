"""Load, validate, summarize, and exact-deduplicate labeled feature CSVs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ml.data.manifest import DatasetManifest, sha256_file
from ml.preprocessing.features import FeatureDataError, validate_feature_frame
from nids_engine.features import FEATURE_NAMES


class DatasetValidationError(ValueError):
    """Raised when the input table cannot be used without leakage or ambiguity."""


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    rows_in_file: int
    rows_after_deduplication: int
    duplicates_removed: int
    capture_group_count: int
    class_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class DatasetBundle:
    features: pd.DataFrame
    labels: pd.Series
    capture_groups: pd.Series
    manifest: DatasetManifest
    summary: DatasetSummary


def load_feature_dataset(csv_path: str | Path, manifest: DatasetManifest) -> DatasetBundle:
    manifest.validate()
    path = Path(csv_path)
    if sha256_file(path) != manifest.prepared_csv_sha256:
        raise DatasetValidationError("prepared CSV SHA-256 does not match its provenance manifest")
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetValidationError(f"could not read feature CSV: {path}") from exc
    if frame.empty:
        raise DatasetValidationError("feature CSV contains no rows")

    expected_columns = set(FEATURE_NAMES) | {manifest.label_column, manifest.capture_group_column}
    actual_columns = set(frame.columns)
    if actual_columns != expected_columns or len(frame.columns) != len(expected_columns):
        missing = sorted(expected_columns - actual_columns)
        unexpected = sorted(actual_columns - expected_columns)
        raise DatasetValidationError(
            f"CSV columns do not match schema; missing={missing}, unexpected={unexpected}"
        )
    frame = frame.loc[:, [*FEATURE_NAMES, manifest.label_column, manifest.capture_group_column]].copy()

    labels = frame[manifest.label_column].astype("string").str.strip()
    groups = frame[manifest.capture_group_column].astype("string").str.strip()
    if labels.isna().any() or labels.eq("").any():
        raise DatasetValidationError("every flow must have a non-empty ground-truth label")
    if groups.isna().any() or groups.eq("").any():
        raise DatasetValidationError("every flow must have a non-empty capture group")

    try:
        features = validate_feature_frame(frame.loc[:, FEATURE_NAMES])
    except FeatureDataError as exc:
        raise DatasetValidationError(str(exc)) from exc

    feature_duplicate_mask = frame.duplicated(subset=list(FEATURE_NAMES), keep=False)
    if feature_duplicate_mask.any():
        duplicate_rows = frame.loc[feature_duplicate_mask, [*FEATURE_NAMES, manifest.label_column]]
        label_counts = duplicate_rows.groupby(list(FEATURE_NAMES), dropna=False)[manifest.label_column].nunique()
        if (label_counts > 1).any():
            raise DatasetValidationError("identical feature vectors have conflicting ground-truth labels")

    rows_in_file = len(frame)
    duplicate_mask = frame.duplicated(subset=[*FEATURE_NAMES, manifest.label_column], keep="first")
    duplicates_removed = int(duplicate_mask.sum())
    if duplicates_removed:
        keep = ~duplicate_mask
        features = features.loc[keep].reset_index(drop=True)
        labels = labels.loc[keep].reset_index(drop=True)
        groups = groups.loc[keep].reset_index(drop=True)
    else:
        features = features.reset_index(drop=True)
        labels = labels.reset_index(drop=True)
        groups = groups.reset_index(drop=True)

    labels = labels.astype(str)
    groups = groups.astype(str)
    class_counts = {str(label): int(count) for label, count in labels.value_counts().sort_index().items()}
    summary = DatasetSummary(
        rows_in_file=rows_in_file,
        rows_after_deduplication=len(features),
        duplicates_removed=duplicates_removed,
        capture_group_count=int(groups.nunique()),
        class_counts=class_counts,
    )
    return DatasetBundle(features, labels, groups, manifest, summary)
