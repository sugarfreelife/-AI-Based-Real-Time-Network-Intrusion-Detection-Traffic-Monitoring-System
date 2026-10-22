# Inference and alert behavior

## PCAP monitor

`python -m nids_engine.monitor --pcap <authorized-file.pcap>` streams an offline capture through the packet parser, bounded flow builder, feature schema, and alert engine. Add `--model <trusted-model.joblib>` to enable classification. The corresponding `.metadata.json` file must be present. Without a model, the output reports `model_missing` and transparent heuristic rules continue to run.

The command prints one JSON line per finalized flow to standard output. Each record contains the flow metadata, 32 schema features, an inference status, and zero or more alerts. The capture summary, model status, and prediction status counts are written to standard error. Model statuses include `scored`, `model_missing`, `model_incompatible`, `model_invalid`, `model_corrupt`, `review_required`, and `inference_error`.

## Model alerts

A successfully scored flow creates an alert when its predicted class is not in the configured benign-label list. The default benign class is `BENIGN`; use `--benign-label VALUE` one or more times when the trained dataset uses other verified labels. The alert records the predicted class, model version, endpoints, protocol, severity, and a reminder to validate against local ground truth.

The system does not report probabilities. Current estimators are not calibrated, so a probability-like value would overstate what the training pipeline establishes.

## Heuristic rules

| Rule | Default trigger | Severity | Evidence |
|---|---|---|---|
| `tcp_syn_burst` | TCP flow has at least 20 SYN packets and zero ACK packets. Set with `--syn-burst-threshold`. | Medium | Observed SYN count, ACK count, and configured threshold. |
| `high_packet_rate` | Flow packet rate is at least 1,000 packets per second. Set with `--high-packets-per-second`. | Medium | Measured packets per second and configured threshold. |

These thresholds are transparent review heuristics. Repeated SYNs can be retransmissions or benign behavior, and high packet rates can be expected for some workloads. They do not prove an intrusion and need evaluation against the intended environment.

## Duplicate suppression and limits

Alerts with the same detection code, protocol, and canonical endpoint pair are suppressed for 60 seconds of flow event time. The in-memory deduplicator is bounded to 50,000 signatures; it is process-local and resets when the monitor exits. Suppression counts appear in the summary. Persistent deduplication and alert acknowledgement are planned for later steps.

The model artifact checksum is checked before joblib loading. A checksum does not authenticate its producer, and joblib may execute code during deserialization. Load only artifacts created by a trusted project training run. No model artifact or real alert evaluation is included because no labeled data was supplied.
