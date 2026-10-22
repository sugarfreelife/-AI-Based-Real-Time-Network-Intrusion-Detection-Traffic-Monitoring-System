"""Train and evaluate the baseline and random-forest models reproducibly."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from joblib import __version__ as joblib_version
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.data.loader import DatasetBundle, load_feature_dataset
from ml.data.manifest import DatasetManifest, sha256_file
from ml.evaluation.metrics import classification_metrics
from ml.training.split import DatasetSplit, split_by_capture_group
from nids_engine.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def _make_models(random_seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=200,
                        max_features="sqrt",
                        class_weight="balanced_subsample",
                        random_state=random_seed,
                        n_jobs=1,
                    ),
                )
            ]
        ),
    }


def _rows(frame: pd.DataFrame, indices: np.ndarray) -> pd.DataFrame:
    return frame.iloc[indices].loc[:, FEATURE_NAMES]


def _labels(series: pd.Series, indices: np.ndarray) -> np.ndarray:
    return series.iloc[indices].astype(str).to_numpy()


def train_and_evaluate(
    dataset: DatasetBundle,
    output_path: str | Path,
    *,
    random_seed: int = 42,
    test_fraction: float = 0.2,
    validation_fraction: float = 0.2,
) -> dict[str, Any]:
    split: DatasetSplit = split_by_capture_group(
        dataset,
        test_fraction=test_fraction,
        validation_fraction=validation_fraction,
        random_seed=random_seed,
    )
    classes = sorted(set(dataset.labels.astype(str)))
    x_train = _rows(dataset.features, split.train_indices)
    y_train = _labels(dataset.labels, split.train_indices)
    x_validation = _rows(dataset.features, split.validation_indices)
    y_validation = _labels(dataset.labels, split.validation_indices)
    x_test = _rows(dataset.features, split.test_indices)
    y_test = _labels(dataset.labels, split.test_indices)

    fitted: dict[str, tuple[Pipeline, float, float]] = {}
    for name, pipeline in _make_models(random_seed).items():
        started = time.perf_counter()
        pipeline.fit(x_train, y_train)
        training_seconds = time.perf_counter() - started
        validation_predictions = pipeline.predict(x_validation)
        validation_macro_f1 = float(
            f1_score(y_validation, validation_predictions, labels=classes, average="macro", zero_division=0)
        )
        fitted[name] = (pipeline, training_seconds, validation_macro_f1)

    # Validation macro-F1 selects the model. The held-out test split is scored once after selection.
    selected_name = max(fitted, key=lambda name: (fitted[name][2], name == "logistic_regression"))
    selected_pipeline, training_seconds, selected_validation_macro_f1 = fitted[selected_name]
    started = time.perf_counter()
    test_predictions = selected_pipeline.predict(x_test)
    test_metrics = classification_metrics(y_test, test_predictions, classes)
    test_evaluation_seconds = time.perf_counter() - started

    now = datetime.now(UTC)
    model_version = f"nids-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    artifact = Path(output_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = artifact.with_suffix(artifact.suffix + ".metadata.json")
    evaluation_path = artifact.with_suffix(artifact.suffix + ".evaluation.json")

    metadata = {
        "model_version": model_version,
        "selected_model": selected_name,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "classes": classes,
        "label_mapping": "identity",
        "dataset": {
            "name": dataset.manifest.dataset_name,
            "source_url": dataset.manifest.source_url,
            "citation": dataset.manifest.citation,
            "prepared_csv_sha256": dataset.manifest.prepared_csv_sha256,
            "upstream_sha256": dataset.manifest.upstream_sha256,
            "rows_in_file": dataset.summary.rows_in_file,
            "rows_after_deduplication": dataset.summary.rows_after_deduplication,
            "duplicates_removed": dataset.summary.duplicates_removed,
            "class_counts": dataset.summary.class_counts,
        },
        "created_at_utc": now.isoformat(),
        "random_seed": random_seed,
        "split_strategy": "two-stage GroupShuffleSplit by capture_group",
        "split_fractions": {
            "train": 1.0 - test_fraction - validation_fraction,
            "validation": validation_fraction,
            "test": test_fraction,
        },
        "training_configuration": {
            "logistic_regression": {
                "max_iter": 2000,
                "class_weight": "balanced",
                "random_state": random_seed,
                "preprocessing": "StandardScaler fitted on training split only",
            },
            "random_forest": {
                "n_estimators": 200,
                "max_features": "sqrt",
                "class_weight": "balanced_subsample",
                "random_state": random_seed,
                "n_jobs": 1,
            },
            "selection_metric": "validation macro-F1; ties prefer logistic regression",
        },
        "split_group_counts": {
            "train": split.train_group_count,
            "validation": split.validation_group_count,
            "test": split.test_group_count,
        },
        "validation_macro_f1_by_model": {name: values[2] for name, values in fitted.items()},
        "selected_validation_macro_f1": selected_validation_macro_f1,
        "training_duration_seconds": training_seconds,
        "training_duration_seconds_by_model": {name: values[1] for name, values in fitted.items()},
        "test_evaluation_duration_seconds": test_evaluation_seconds,
        "scikit_learn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "artifact_trust": "Load only artifacts produced and verified by this project.",
    }
    evaluation = {
        "model_version": model_version,
        "selected_model": selected_name,
        "evaluation_split": "held-out capture groups; not used for model selection",
        **test_metrics,
    }
    joblib.dump(selected_pipeline, artifact)
    metadata["model_artifact_sha256"] = sha256_file(artifact)
    metadata["joblib_version"] = joblib_version
    metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    evaluation_path.write_text(json.dumps(evaluation, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {
        "model_version": model_version,
        "selected_model": selected_name,
        "validation_macro_f1_by_model": metadata["validation_macro_f1_by_model"],
        "selected_validation_macro_f1": selected_validation_macro_f1,
        "evaluation": evaluation,
        "artifact_path": str(artifact),
        "metadata_path": str(metadata_path),
        "evaluation_path": str(evaluation_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train a project-schema NIDS model using capture-group splits.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args(argv)

    manifest = DatasetManifest.from_file(args.manifest)
    dataset = load_feature_dataset(args.csv, manifest)
    result = train_and_evaluate(
        dataset,
        args.output,
        random_seed=args.random_seed,
        test_fraction=args.test_fraction,
        validation_fraction=args.validation_fraction,
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
