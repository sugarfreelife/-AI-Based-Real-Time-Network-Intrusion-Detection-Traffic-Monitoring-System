# Machine-learning methodology

## Current status

Step 4 builds the data export, validation, split, training, and evaluation pipeline. No research dataset or trained model is included in the repository. Synthetic rows exist only in tests; their scores are not research results and are not published as model metrics.

## Feature compatibility

Training rows must contain the exact ordered schema documented in [FEATURE_SCHEMA.md](FEATURE_SCHEMA.md), plus `label` and `capture_group`. The label is ground truth and the capture group identifies an independent capture. Neither is model input. Any extra column, including an identifier or timestamp, is rejected rather than silently dropped.

CICIDS2017 is an acquisition candidate, not a drop-in training table: the official dataset uses more than 80 CICFlowMeter features while this project's inference schema is different. Feature rows must be regenerated or accurately transformed to the project schema and verified against its calculations. The source's file-level PCAP/CSV mapping is not assumed.

## Validation and leakage controls

- Validate exact feature names and order, numeric types, finite/non-negative values, integer-valued counts/ports, protocol one-hot fields, port ranges, and directional totals.
- Reject empty labels/groups and verify the prepared CSV checksum against its provenance manifest.
- Detect and remove exact feature-plus-label duplicates before splitting; reject identical feature vectors with conflicting labels. Near-duplicate detection is not implemented and must be considered when the source has derived or repeated flows.
- Split by `capture_group` using deterministic `GroupShuffleSplit`; no capture group can appear in more than one split. The split fails if any class is missing from a split.
- Fit `StandardScaler` only on training data inside a Logistic Regression pipeline. Random Forest receives the numeric schema directly.
- Apply class weights to both models. Select by validation macro-F1; score the selected model once on held-out test groups.

## Models and reporting

The baseline is class-weighted Logistic Regression. The comparison model is a class-weighted Random Forest. Saved metadata includes model/schema version, feature order, dataset name and checksum, upstream checksums when known, class counts, split strategy and group counts, random seed, package versions, model artifact SHA-256, a SHA-256 for the held-out report, configuration, and measured durations. Inference checks the artifact checksum and exact scikit-learn/joblib versions before deserialization, then checks fitted feature order and class names. A checksum detects changes against the sidecar but is not a signature; load only artifacts whose source the operator trusts because joblib deserializes Python objects. The authenticated model status API exposes selected metadata and displays only schema-valid held-out reports whose checksum and model identity match. This is an integrity check, not a signature or proof that the supplied labels are correct. The held-out report includes accuracy, macro precision/recall/F1, per-class metrics, support, and a confusion matrix.

The current estimators do not produce calibrated probabilities. Inference reports only the predicted class and does not expose a confidence score.

No metrics are available until real labeled capture groups are prepared. Offline performance does not establish equivalent performance on live traffic; dataset-to-live distribution shift and ground-truth quality must be discussed.
