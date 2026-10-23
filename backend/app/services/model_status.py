"""Expose configured model metadata only after project artifact verification."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any

from backend.app.schemas import EvaluationReportRead, ModelMetadataRead, ModelStatusRead

logger = logging.getLogger("backend.model_status")


def _status(
    status: str,
    *,
    configured: bool,
    message: str,
    evaluation_status: str = "not_available",
    model: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ModelStatusRead(
        status=status,
        configured=configured,
        message=message,
        evaluation_status=evaluation_status,
        model=model,
        evaluation=evaluation,
    ).model_dump(mode="json")


def inspect_configured_model(model_path: str | None) -> dict[str, Any]:
    """Validate the configured artifact and expose its matching held-out report.

    The configured path is an operator trust decision: project validation checks
    metadata, compatibility, and checksums before joblib deserialization, but a
    checksum is not a cryptographic signature for an untrusted artifact.
    """

    if not model_path:
        return _status(
            "not_configured",
            configured=False,
            message="No model is configured. Heuristic detections remain available.",
        )

    try:
        from ml.data.manifest import sha256_file
        from nids_engine.features import FEATURE_NAMES
        from nids_engine.inference import ModelArtifactError, load_trusted_model
    except ModuleNotFoundError:
        return _status(
            "model_incompatible",
            configured=True,
            message="The model runtime dependencies are not installed in the API environment.",
        )

    try:
        trusted_model = load_trusted_model(model_path)
        metadata = json.loads(trusted_model.metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("model metadata must be an object")
        dataset = metadata.get("dataset")
        if not isinstance(dataset, dict):
            raise ValueError("model dataset provenance is missing")
        model = ModelMetadataRead(
            model_version=trusted_model.model_version,
            selected_model=metadata["selected_model"],
            feature_schema_version=metadata["feature_schema_version"],
            feature_count=len(FEATURE_NAMES),
            classes=list(trusted_model.classes),
            created_at_utc=metadata.get("created_at_utc"),
            dataset_name=dataset["name"],
            dataset_rows=dataset["rows_after_deduplication"],
            dataset_sha256=dataset["prepared_csv_sha256"],
            artifact_sha256=metadata["model_artifact_sha256"],
        ).model_dump(mode="json")
    except ModelArtifactError as exc:
        return _status(
            str(exc.status),
            configured=True,
            message=str(exc),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("configured_model_metadata_invalid", extra={"error_type": type(exc).__name__})
        return _status(
            "model_invalid",
            configured=True,
            message="The configured model metadata is incomplete or invalid.",
        )
    except Exception:
        logger.exception("configured_model_inspection_failed")
        return _status(
            "model_invalid",
            configured=True,
            message="The configured model could not be verified.",
        )

    artifact = Path(model_path)
    evaluation_path = artifact.with_suffix(artifact.suffix + ".evaluation.json")
    if not evaluation_path.is_file():
        return _status(
            "ready",
            configured=True,
            message="The configured model passed project artifact checks.",
            evaluation_status="missing",
            model=model,
        )

    expected_report_digest = metadata.get("evaluation_report_sha256")
    if not isinstance(expected_report_digest, str) or len(expected_report_digest) != 64:
        return _status(
            "ready",
            configured=True,
            message="The configured model passed project artifact checks.",
            evaluation_status="unverified",
            model=model,
        )

    try:
        if sha256_file(evaluation_path) != expected_report_digest.lower():
            raise ValueError("evaluation report checksum does not match the model metadata")
        payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        report = EvaluationReportRead.model_validate(payload)
        if (
            report.model_version != trusted_model.model_version
            or report.selected_model != metadata["selected_model"]
            or not report.evaluation_split.startswith("held-out capture groups")
        ):
            raise ValueError("evaluation report does not match the configured model")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _status(
            "ready",
            configured=True,
            message="The configured model passed artifact checks, but its evaluation report could not be verified.",
            evaluation_status="invalid",
            model=model,
        )

    return _status(
        "ready",
        configured=True,
        message="The configured model and its held-out evaluation report passed integrity checks.",
        evaluation_status="verified",
        model=model,
        evaluation=report.model_dump(mode="json"),
    )


class ModelStatusProvider:
    """Resolve model files once per API process; restart after changing artifacts."""

    def __init__(self, model_path: str | None) -> None:
        self.model_path = model_path
        self._value: dict[str, Any] | None = None
        self._lock = Lock()

    def get(self) -> dict[str, Any]:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = inspect_configured_model(self.model_path)
        return deepcopy(self._value)
