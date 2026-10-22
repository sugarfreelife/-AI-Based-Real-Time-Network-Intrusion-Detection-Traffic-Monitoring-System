"""Load project-produced models and classify validated flow features."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ml.data.manifest import sha256_file
from nids_engine.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, FeatureSchemaError, extract_features
from nids_engine.flows import FlowRecord


class ModelArtifactStatus(StrEnum):
    MISSING = "model_missing"
    INVALID = "model_invalid"
    INCOMPATIBLE = "model_incompatible"
    CORRUPT = "model_corrupt"


class ModelArtifactError(ValueError):
    """A model artifact cannot be used for inference."""

    def __init__(self, status: ModelArtifactStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class TrustedModel:
    pipeline: Pipeline
    model_version: str
    classes: tuple[str, ...]
    artifact_path: Path
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class PredictionResult:
    flow_id: str
    status: str
    predicted_label: str | None
    model_version: str | None
    feature_schema_version: str
    predicted_at_utc: str
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_trusted_model(artifact_path: str | Path) -> TrustedModel:
    """Load a checksum-matched project pipeline after validating its metadata.

    Joblib uses pickle serialization. The checksum detects accidental changes;
    it does not make an untrusted artifact safe to deserialize. Callers must
    supply a model produced by this project's training pipeline and trust its
    source before this function is called.
    """

    artifact = Path(artifact_path)
    metadata_path = artifact.with_suffix(artifact.suffix + ".metadata.json")
    if not artifact.is_file() or not metadata_path.is_file():
        raise ModelArtifactError(ModelArtifactStatus.MISSING, "model artifact or metadata file is missing")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model metadata is unreadable") from exc
    if not isinstance(metadata, dict):
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model metadata must be a JSON object")

    required = (
        "model_version",
        "selected_model",
        "feature_schema_version",
        "feature_names",
        "classes",
        "model_artifact_sha256",
        "artifact_trust",
        "scikit_learn_version",
        "joblib_version",
    )
    if any(key not in metadata for key in required):
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model metadata is missing required fields")
    if metadata["artifact_trust"] != "Load only artifacts produced and verified by this project.":
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model metadata does not identify a trusted project artifact")
    try:
        if metadata["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
            raise ModelArtifactError(ModelArtifactStatus.INCOMPATIBLE, "model feature schema version is incompatible")
        if tuple(metadata["feature_names"]) != FEATURE_NAMES:
            raise ModelArtifactError(ModelArtifactStatus.INCOMPATIBLE, "model feature names or order are incompatible")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ModelArtifactError):
            raise
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model feature metadata is invalid") from exc

    classes_value = metadata["classes"]
    model_version = metadata["model_version"]
    if (
        not isinstance(classes_value, list)
        or not classes_value
        or any(not isinstance(label, str) or not label for label in classes_value)
        or len(set(classes_value)) != len(classes_value)
        or not isinstance(model_version, str)
        or not model_version.strip()
    ):
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model classes or version metadata is invalid")
    if metadata["scikit_learn_version"] != sklearn.__version__ or metadata["joblib_version"] != joblib.__version__:
        raise ModelArtifactError(
            ModelArtifactStatus.INCOMPATIBLE,
            "model was produced with different scikit-learn or joblib versions",
        )
    expected_digest = metadata["model_artifact_sha256"]
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "model artifact checksum metadata is invalid")
    try:
        actual_digest = sha256_file(artifact)
    except OSError as exc:
        raise ModelArtifactError(ModelArtifactStatus.MISSING, "model artifact cannot be read") from exc
    if actual_digest != expected_digest.lower():
        raise ModelArtifactError(ModelArtifactStatus.CORRUPT, "model artifact checksum does not match metadata")

    try:
        pipeline = joblib.load(artifact)
    except Exception as exc:
        raise ModelArtifactError(ModelArtifactStatus.CORRUPT, "model artifact could not be deserialized") from exc
    if not isinstance(pipeline, Pipeline) or "classifier" not in pipeline.named_steps:
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "artifact is not a supported project pipeline")
    classifier = pipeline.named_steps["classifier"]
    if not isinstance(classifier, (LogisticRegression, RandomForestClassifier)):
        raise ModelArtifactError(ModelArtifactStatus.INVALID, "pipeline classifier type is not supported")
    pipeline_names = getattr(pipeline, "feature_names_in_", None)
    if pipeline_names is None or tuple(str(name) for name in pipeline_names) != FEATURE_NAMES:
        raise ModelArtifactError(ModelArtifactStatus.INCOMPATIBLE, "model's fitted feature names or order are incompatible")
    fitted_classes = tuple(str(label) for label in getattr(pipeline, "classes_", ()))
    if fitted_classes != tuple(classes_value):
        raise ModelArtifactError(ModelArtifactStatus.INCOMPATIBLE, "model classes do not match its metadata")
    return TrustedModel(pipeline, model_version.strip(), fitted_classes, artifact, metadata_path)


class InferenceEngine:
    """Keep inference available as a structured degraded state when no model loads."""

    def __init__(self, model: TrustedModel | None = None, error: ModelArtifactError | None = None) -> None:
        self.model = model
        self.error = error

    @classmethod
    def from_path(cls, artifact_path: str | Path | None) -> InferenceEngine:
        if artifact_path is None:
            return cls(error=ModelArtifactError(ModelArtifactStatus.MISSING, "no model path was configured"))
        try:
            return cls(model=load_trusted_model(artifact_path))
        except ModelArtifactError as exc:
            return cls(error=exc)

    @property
    def status(self) -> str:
        if self.model is not None:
            return "ready"
        return self.error.status.value if self.error is not None else ModelArtifactStatus.INVALID.value

    @property
    def model_version(self) -> str | None:
        return self.model.model_version if self.model else None

    def predict(self, flow: FlowRecord) -> PredictionResult:
        predicted_at = datetime.now(UTC).isoformat()
        if self.model is None:
            return PredictionResult(
                flow.flow_id,
                self.status,
                None,
                None,
                FEATURE_SCHEMA_VERSION,
                predicted_at,
                "model_unavailable",
            )
        try:
            feature_vector = extract_features(flow)
            frame = pd.DataFrame([feature_vector.as_dict()], columns=FEATURE_NAMES)
            predicted = self.model.pipeline.predict(frame)
            if len(predicted) != 1:
                raise ValueError("classifier returned an unexpected prediction count")
            label = str(predicted[0])
            if label not in self.model.classes:
                raise ValueError("classifier returned a label outside its fitted classes")
        except FeatureSchemaError:
            return PredictionResult(
                flow.flow_id, "review_required", None, self.model.model_version,
                FEATURE_SCHEMA_VERSION, predicted_at, "feature_validation_failed",
            )
        except Exception:
            logging.getLogger("nids_engine.inference").exception("model_inference_failed")
            return PredictionResult(
                flow.flow_id, "inference_error", None, self.model.model_version,
                FEATURE_SCHEMA_VERSION, predicted_at, "model_prediction_failed",
            )
        return PredictionResult(
            flow.flow_id, "scored", label, self.model.model_version,
            FEATURE_SCHEMA_VERSION, predicted_at,
        )
