from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from scapy.layers.inet import IP, TCP
from scapy.utils import wrpcap

from ml.data.combine_features import combine_csvs
from ml.data.exporter import LabelMappingError, export_labeled_features, extract_flows, write_label_template
from ml.data.loader import DatasetValidationError, load_feature_dataset
from ml.data.manifest import DatasetManifest, build_manifest, sha256_file, write_manifest
from ml.training.split import split_by_capture_group
from ml.training.train import train_and_evaluate
from nids_engine.detection import AlertDeduplicator, AlertEngine
from nids_engine.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from nids_engine.flows import FlowBuilder
from nids_engine.inference import InferenceEngine, ModelArtifactStatus, PredictionResult, load_trusted_model
from nids_engine.monitor import main as monitor_main
from nids_engine.packet import PacketMetadata
from backend.app.services.model_status import inspect_configured_model


CLASSES = ("BENIGN", "ATTACK_A", "ATTACK_B")


def feature_row(group_index: int, class_index: int) -> dict[str, float | str]:
    duration = float(5 + group_index + class_index)
    total_packets = 6 + class_index
    forward_packets = 4 + class_index
    reverse_packets = total_packets - forward_packets
    forward_bytes = 400 + (group_index * 2) + class_index * 50
    reverse_bytes = 200 + class_index * 25
    total_bytes = forward_bytes + reverse_bytes
    row: dict[str, float | str] = {name: 0.0 for name in FEATURE_NAMES}
    row.update(
        {
            "flow_duration_seconds": duration,
            "total_packets": float(total_packets),
            "total_bytes": float(total_bytes),
            "forward_packets": float(forward_packets),
            "reverse_packets": float(reverse_packets),
            "forward_bytes": float(forward_bytes),
            "reverse_bytes": float(reverse_bytes),
            "packets_per_second": total_packets / duration,
            "bytes_per_second": total_bytes / duration,
            "average_packet_size": total_bytes / total_packets,
            "min_packet_size": 60.0,
            "max_packet_size": 140.0,
            "protocol_tcp": 1.0,
            "endpoint_a_port": float((80, 23, 3389)[class_index]),
            "endpoint_a_port_missing": 0.0,
            "endpoint_b_port": 49152.0,
            "endpoint_b_port_missing": 0.0,
            "tcp_syn_count": 1.0 + float(class_index),
            "tcp_ack_count": float(total_packets - 1),
            "forward_packet_size_min": 60.0,
            "forward_packet_size_max": 140.0,
            "forward_packet_size_missing": 0.0,
            "reverse_packet_size_min": 60.0,
            "reverse_packet_size_max": 100.0,
            "reverse_packet_size_missing": 0.0,
        }
    )
    row["label"] = CLASSES[class_index]
    row["capture_group"] = f"capture-{group_index:02d}"
    return row


def fixture_csv(tmp_path: Path, *, group_count: int = 30, extra_columns: bool = False) -> Path:
    rows = [feature_row(group_index, class_index) for group_index in range(group_count) for class_index in range(3)]
    frame = pd.DataFrame(rows, columns=[*FEATURE_NAMES, "label", "capture_group"])
    if extra_columns:
        frame["flow_id"] = [f"flow-{index}" for index in range(len(frame))]
    path = tmp_path / "labeled-features.csv"
    frame.to_csv(path, index=False)
    return path


def manifest_for(path: Path) -> DatasetManifest:
    return build_manifest(
        path,
        dataset_name="synthetic unit-test fixture",
        source_url="urn:nids-test-fixture",
        citation="Synthetic data for software tests only; not a research dataset.",
    )


def test_manifest_round_trip_and_dataset_summary(tmp_path) -> None:
    path = fixture_csv(tmp_path)
    manifest = manifest_for(path)
    manifest_path = write_manifest(manifest, tmp_path / "manifest.json")
    loaded_manifest = DatasetManifest.from_file(manifest_path)
    dataset = load_feature_dataset(path, loaded_manifest)

    assert loaded_manifest.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert dataset.summary.rows_in_file == 90
    assert dataset.summary.rows_after_deduplication == 90
    assert dataset.summary.capture_group_count == 30
    assert dataset.summary.class_counts == {"ATTACK_A": 30, "ATTACK_B": 30, "BENIGN": 30}


def test_group_split_is_deterministic_and_has_no_group_overlap(tmp_path) -> None:
    path = fixture_csv(tmp_path)
    dataset = load_feature_dataset(path, manifest_for(path))

    first = split_by_capture_group(dataset, random_seed=17)
    second = split_by_capture_group(dataset, random_seed=17)

    assert first.train_indices.tolist() == second.train_indices.tolist()
    assert first.validation_indices.tolist() == second.validation_indices.tolist()
    assert first.test_indices.tolist() == second.test_indices.tolist()
    groups = dataset.capture_groups.to_numpy()
    train_groups = set(groups[first.train_indices])
    validation_groups = set(groups[first.validation_indices])
    test_groups = set(groups[first.test_indices])
    assert not train_groups & validation_groups
    assert not train_groups & test_groups
    assert not validation_groups & test_groups
    for indices in (first.train_indices, first.validation_indices, first.test_indices):
        assert set(dataset.labels.iloc[indices]) == set(CLASSES)


def test_exact_duplicates_are_removed_before_split(tmp_path) -> None:
    rows = [feature_row(group, class_index) for group in range(30) for class_index in range(3)]
    duplicate = dict(rows[0])
    duplicate["capture_group"] = "another-capture"
    rows.append(duplicate)
    path = tmp_path / "duplicates.csv"
    pd.DataFrame(rows, columns=[*FEATURE_NAMES, "label", "capture_group"]).to_csv(path, index=False)

    dataset = load_feature_dataset(path, manifest_for(path))

    assert dataset.summary.rows_in_file == 91
    assert dataset.summary.rows_after_deduplication == 90
    assert dataset.summary.duplicates_removed == 1


def test_identical_features_with_conflicting_labels_are_rejected(tmp_path) -> None:
    rows = [feature_row(group, class_index) for group in range(30) for class_index in range(3)]
    conflict = dict(rows[0])
    conflict["label"] = "ATTACK_A"
    conflict["capture_group"] = "different-capture"
    rows.append(conflict)
    path = tmp_path / "conflict.csv"
    pd.DataFrame(rows, columns=[*FEATURE_NAMES, "label", "capture_group"]).to_csv(path, index=False)

    with pytest.raises(DatasetValidationError, match="conflicting"):
        load_feature_dataset(path, manifest_for(path))


def test_extra_identifier_columns_are_rejected(tmp_path) -> None:
    path = fixture_csv(tmp_path, extra_columns=True)

    with pytest.raises(DatasetValidationError, match="unexpected"):
        load_feature_dataset(path, manifest_for(path))


def test_manifest_hash_mismatch_is_rejected(tmp_path) -> None:
    path = fixture_csv(tmp_path)
    manifest = manifest_for(path)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="SHA-256"):
        load_feature_dataset(path, manifest)


def test_group_split_requires_multiple_independent_captures(tmp_path) -> None:
    path = fixture_csv(tmp_path, group_count=3)
    dataset = load_feature_dataset(path, manifest_for(path))

    with pytest.raises(DatasetValidationError, match="at least 5"):
        split_by_capture_group(dataset)


def test_training_saves_metadata_and_heldout_report(tmp_path) -> None:
    path = fixture_csv(tmp_path)
    dataset = load_feature_dataset(path, manifest_for(path))
    artifact = tmp_path / "models" / "fixture.joblib"

    result = train_and_evaluate(dataset, artifact, random_seed=23)

    assert artifact.exists()
    metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
    evaluation = json.loads(Path(result["evaluation_path"]).read_text(encoding="utf-8"))
    assert metadata["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert metadata["selected_model"] in {"logistic_regression", "random_forest"}
    assert metadata["split_strategy"].startswith("two-stage GroupShuffleSplit")
    assert evaluation["evaluation_split"].startswith("held-out capture groups")
    assert set(evaluation["classes"]) == set(CLASSES)
    assert set(evaluation["support"]) == set(CLASSES)
    assert result["model_version"] == evaluation["model_version"]
    assert metadata["model_artifact_sha256"]
    assert metadata["evaluation_report_sha256"] == sha256_file(result["evaluation_path"])
    assert metadata["joblib_version"]

    model_status = inspect_configured_model(str(artifact))
    assert model_status["status"] == "ready"
    assert model_status["evaluation_status"] == "verified"
    assert model_status["model"]["model_version"] == result["model_version"]
    assert model_status["evaluation"]["evaluation_split"].startswith("held-out capture groups")

    model = load_trusted_model(artifact)
    assert model.model_version == result["model_version"]
    flow = _make_flow()
    prediction = InferenceEngine.from_path(artifact).predict(flow)
    assert prediction.status == "scored"
    assert prediction.predicted_label in CLASSES

    Path(result["evaluation_path"]).write_text(
        Path(result["evaluation_path"]).read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    tampered_status = inspect_configured_model(str(artifact))
    assert tampered_status["status"] == "ready"
    assert tampered_status["evaluation_status"] == "invalid"
    assert tampered_status["evaluation"] is None


def _make_flow(*, syn_count: int = 1, start_second: int = 1_700_000_000):
    builder = FlowBuilder()
    for index in range(syn_count):
        builder.process(PacketMetadata(
            timestamp=datetime.fromtimestamp(start_second + index, tz=UTC),
            src_ip="192.0.2.10",
            dst_ip="198.51.100.20",
            src_port=41000,
            dst_port=443,
            protocol="TCP",
            packet_length=60,
            ip_version=4,
            tcp_flags=0x02,
        ))
    [flow] = builder.flush()
    return flow


def _prediction(flow_id: str, status: str, label: str | None = None) -> PredictionResult:
    return PredictionResult(
        flow_id=flow_id,
        status=status,
        predicted_label=label,
        model_version="test-model" if status == "scored" else None,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        predicted_at_utc=datetime.now(UTC).isoformat(),
    )


def test_missing_or_incompatible_models_return_explicit_status(tmp_path) -> None:
    flow = _make_flow()
    missing = InferenceEngine.from_path(tmp_path / "missing.joblib")
    result = missing.predict(flow)
    assert missing.status == ModelArtifactStatus.MISSING.value
    assert result.status == ModelArtifactStatus.MISSING.value
    assert result.predicted_label is None
    assert result.reason == "model_unavailable"

    artifact = tmp_path / "invalid.joblib"
    artifact.write_bytes(b"not deserialized because schema is incompatible")
    metadata_path = artifact.with_suffix(".joblib.metadata.json")
    metadata_path.write_text(json.dumps({
        "model_version": "old-model",
        "selected_model": "logistic_regression",
        "feature_schema_version": "0.9",
        "feature_names": list(FEATURE_NAMES),
        "classes": list(CLASSES),
        "model_artifact_sha256": "0" * 64,
        "artifact_trust": "Load only artifacts produced and verified by this project.",
        "scikit_learn_version": "not-reached",
        "joblib_version": "not-reached",
    }), encoding="utf-8")
    incompatible = InferenceEngine.from_path(artifact)
    assert incompatible.status == ModelArtifactStatus.INCOMPATIBLE.value
    assert incompatible.predict(flow).status == ModelArtifactStatus.INCOMPATIBLE.value


def test_model_checksum_rejects_changed_artifact(tmp_path) -> None:
    path = fixture_csv(tmp_path)
    dataset = load_feature_dataset(path, manifest_for(path))
    artifact = tmp_path / "models" / "fixture.joblib"
    train_and_evaluate(dataset, artifact, random_seed=23)
    with artifact.open("ab") as output:
        output.write(b"changed")

    engine = InferenceEngine.from_path(artifact)
    assert engine.status == ModelArtifactStatus.CORRUPT.value


def test_alert_engine_explains_model_and_rule_alerts_and_suppresses_duplicates() -> None:
    flow = _make_flow(syn_count=3)
    engine = AlertEngine(
        benign_labels=("BENIGN",),
        syn_burst_threshold=3,
        high_packet_rate_threshold=1_000_000_000,
        deduplicator=AlertDeduplicator(max_entries=4),
    )
    alerts = engine.evaluate(flow, _prediction(flow.flow_id, "scored", "ATTACK_A"))
    assert [alert.detection_code for alert in alerts] == ["ml_classification:ATTACK_A", "tcp_syn_burst"]
    assert all(alert.explanation and alert.evidence for alert in alerts)
    assert alerts[0].model_version == "test-model"
    assert alerts[1].evidence == {"tcp_syn_count": 3, "tcp_ack_count": 0, "threshold": 3}

    duplicate_flow = _make_flow(syn_count=3)
    repeated = engine.evaluate(duplicate_flow, _prediction(duplicate_flow.flow_id, "scored", "ATTACK_A"))
    assert repeated == []
    assert engine.suppressed_count == 2


def test_benign_predictions_do_not_create_ml_alerts_and_rules_work_without_model() -> None:
    flow = _make_flow(syn_count=3)
    engine = AlertEngine(syn_burst_threshold=3, high_packet_rate_threshold=1_000_000_000)
    benign_alerts = engine.evaluate(flow, _prediction(flow.flow_id, "scored", "BENIGN"))
    assert [alert.detection_code for alert in benign_alerts] == ["tcp_syn_burst"]

    unavailable_alerts = engine.evaluate(
        flow,
        _prediction(flow.flow_id, ModelArtifactStatus.MISSING.value),
    )
    assert unavailable_alerts == []


def test_monitor_replays_pcap_through_rule_alerts_without_a_model(tmp_path, capsys) -> None:
    pcap_path = tmp_path / "syn-burst.pcap"
    wrpcap(
        str(pcap_path),
        [IP(src="192.0.2.10", dst="198.51.100.20") / TCP(sport=41000, dport=443, flags="S") for _ in range(3)],
    )

    result = monitor_main([
        "--pcap", str(pcap_path),
        "--syn-burst-threshold", "3",
        "--high-packets-per-second", "1000000000",
    ])

    captured = capsys.readouterr()
    record = json.loads(captured.out.strip().splitlines()[0])
    summary = json.loads(captured.err.strip())["monitor_summary"]
    assert result == 0
    assert record["prediction"]["status"] == ModelArtifactStatus.MISSING.value
    assert [alert["detection_code"] for alert in record["alerts"]] == ["tcp_syn_burst"]
    assert summary["flows"] == 1
    assert summary["unscored"] == 1
    assert summary["prediction_status_counts"] == {ModelArtifactStatus.MISSING.value: 1}
    assert summary["model_status"] == ModelArtifactStatus.MISSING.value


def test_monitor_connects_pcap_inference_to_model_alerts(tmp_path, capsys) -> None:
    csv_path = fixture_csv(tmp_path)
    dataset = load_feature_dataset(csv_path, manifest_for(csv_path))
    artifact = tmp_path / "models" / "fixture.joblib"
    train_and_evaluate(dataset, artifact, random_seed=23)
    pcap_path = tmp_path / "one-flow.pcap"
    wrpcap(
        str(pcap_path),
        [IP(src="192.0.2.10", dst="198.51.100.20") / TCP(sport=41000, dport=443, flags="S")],
    )

    result = monitor_main([
        "--pcap", str(pcap_path),
        "--model", str(artifact),
        "--benign-label", "NO_TRAINED_CLASS_HAS_THIS_NAME",
        "--high-packets-per-second", "1000000000",
    ])

    captured = capsys.readouterr()
    record = json.loads(captured.out.strip().splitlines()[0])
    assert result == 0
    assert record["prediction"]["status"] == "scored"
    assert record["prediction"]["model_version"]
    assert record["alerts"][0]["source"] == "machine_learning"
    assert record["alerts"][0]["detection_code"] == (
        f"ml_classification:{record['prediction']['predicted_label']}"
    )


def test_export_requires_complete_ground_truth_and_preserves_capture_group(tmp_path) -> None:
    pcap_path = tmp_path / "labeled.pcap"
    wrpcap(
        str(pcap_path),
        [
            IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=12000, dport=443, flags="S"),
            IP(src="198.51.100.2", dst="192.0.2.1") / TCP(sport=443, dport=12000, flags="A"),
        ],
    )
    flows, stats = extract_flows(pcap_path)
    template_path = write_label_template(flows, tmp_path / "labels-template.csv")
    template = pd.read_csv(template_path)
    assert len(template) == 1
    assert template.loc[0, "label"] is None or pd.isna(template.loc[0, "label"])
    labels = {flows[0].flow_id: "BENIGN"}

    with pytest.raises(LabelMappingError, match="exactly"):
        export_labeled_features(flows, {}, "authorized-capture-a", tmp_path / "missing.csv")
    assert stats.status == "completed"
    output_path = export_labeled_features(flows, labels, "authorized-capture-a", tmp_path / "features.csv")
    frame = pd.read_csv(output_path)
    assert len(frame) == 1
    assert frame.loc[0, "label"] == "BENIGN"
    assert frame.loc[0, "capture_group"] == "authorized-capture-a"
    assert list(frame.columns) == [*FEATURE_NAMES, "label", "capture_group"]


def test_combine_keeps_project_schema_order(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    pd.DataFrame([feature_row(0, 0)], columns=[*FEATURE_NAMES, "label", "capture_group"]).to_csv(first, index=False)
    pd.DataFrame([feature_row(1, 1)], columns=[*FEATURE_NAMES, "label", "capture_group"]).to_csv(second, index=False)

    combined, count = combine_csvs([first, second], tmp_path / "combined.csv")
    result = pd.read_csv(combined)

    assert count == 2
    assert list(result.columns) == [*FEATURE_NAMES, "label", "capture_group"]
    assert set(result["capture_group"]) == {"capture-00", "capture-01"}


def test_combine_does_not_overwrite_input_or_partial_destination(tmp_path) -> None:
    source = tmp_path / "source.csv"
    frame = pd.DataFrame([feature_row(0, 0)], columns=[*FEATURE_NAMES, "label", "capture_group"])
    frame.to_csv(source, index=False)
    original_source = source.read_bytes()
    with pytest.raises(ValueError, match="overwrite an input"):
        combine_csvs([source], source)
    assert source.read_bytes() == original_source

    invalid = tmp_path / "invalid.csv"
    invalid.write_text("wrong,header\nvalue,other\n", encoding="utf-8")
    destination = tmp_path / "combined.csv"
    destination.write_text("previous result\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected feature CSV header"):
        combine_csvs([source, invalid], destination)
    assert destination.read_text(encoding="utf-8") == "previous result\n"
