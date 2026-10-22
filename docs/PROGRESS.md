# Progress

## Step 1 of 10 — Audit and foundation

**Status:** Complete and pushed to the user-provided GitHub repository. At the end of Step 1, no NIDS application component was implemented yet.

### Starting state

- Workspace: `D:\Projects\CN`; it contained no files and was not a Git repository.
- OS: Windows (PowerShell).
- Git is installed; Git user name and email are configured locally.
- At initial audit, no Git remote was configured and GitHub CLI was unavailable. The user later provided the repository URL and `origin` was configured.
- Python 3.14.3, Node.js 24.14.1, npm 11.11.0, Docker CLI 29.7.2, and Docker Compose 5.5.0 are installed.
- Available Python packages detected: FastAPI, Pydantic, SQLAlchemy, Alembic, and pytest.
- Not detected: Scapy, Pandas, NumPy, and scikit-learn.
- Docker CLI cannot connect to the Docker Desktop Linux engine (`permission denied` on its named pipe).
- Npcap service was not detected; live capture is not currently verified as available.
- PostgreSQL command-line client was not detected. PostgreSQL server availability has not been established.
- Free space on D: was approximately 270.7 GB at audit time.
- No existing source files or tests were present. No application test suite has been run.

### Work in this step

- [x] Read the supplied build prompt and extract its requirements.
- [x] Inspect repository and runtime starting state.
- [x] Add initial project documentation and safe Git/environment defaults.
- [x] Initialize Git and create the Step 1 commit.
- [x] Push the commit after the GitHub remote is provided and reachable.

### Commands and results

- `git status --short --branch`: failed because the workspace was not a Git repository (expected starting condition).
- Runtime and package discovery: completed; results are listed above.
- Docker engine query: blocked by named-pipe permission denied.
- `python -m pytest --version`: pytest 9.1.1 is installed, although the Python launcher emitted a location warning; no tests existed to run.
- GitHub remote lookup initially had no URL; the user provided the destination during the task.
- Step 1 commit `cad3edf` was pushed to `origin/main` on the user-provided GitHub repository.

### Next task

Step 1 commit `cad3edf` is on GitHub. The next task was Step 2 (packet parsing and offline PCAP replay).

## Step 2 of 10 — Packet ingestion and replay

**Status:** Implemented, verified, committed as `5c5530d`, and pushed to `origin/main`.

### Delivered

- Scapy packet metadata parser for IPv4/IPv6, TCP, UDP, ICMP/ICMPv6, unknown protocols, and non-IP frames.
- Streaming PCAP and PCAPNG replay with protocol filtering and per-run status/counters.
- Optional live capture that requires an explicit interface, supports a BPF filter and protocol filter, and uses Scapy with packet storage disabled.
- JSON-lines packet output and structured JSON lifecycle logs from `python -m nids_engine.replay`.
- Pinned Scapy/Pytest dependencies and a development lock file.
- Ten initial controlled tests, then one fresh-process CLI regression test and one PCAPNG replay test.

### Verification

- `.venv\Scripts\python.exe -m pytest`: PASS, 12 tests.
- `.venv\Scripts\python.exe -m compileall -q nids_engine tests`: PASS.
- `.venv\Scripts\python.exe -m nids_engine.replay --help`: PASS.
- Fresh-process CLI replay test confirms IP/TCP decoding and that a payload marker is absent from output: PASS.
- PCAPNG replay: PASS.
- Live capture: NOT TESTED; Npcap/libpcap support is not available on this host.
- Initial test runs exposed sandbox temp-directory and packet-linktype initialization issues; both were fixed and the final suite passed.
- Dependency installation required approved network access and was placed under the ignored project `.venv`. The base Python launcher warns that it cannot resolve its configured interpreter path; the local environment's Python executable still runs tests.

### Next task

Step 2 is complete on GitHub. The next task is Step 3 (bidirectional flows and versioned features).

## Step 3 of 10 — Bidirectional flows and feature schema

**Status:** Implemented, verified, committed as `85324ba`, and pushed to `origin/main`.

### Delivered

- Canonical IPv4/IPv6 endpoint keys and stable directional A-to-B/B-to-A counters.
- Packet/byte totals, directional size statistics, TCP flag counts, UTC start/last-seen/end timestamps, duration, and finalization reasons.
- Idle and active timeouts driven by a monotonic event-time watermark, including out-of-order packet timestamps.
- A maximum active-flow count and a periodically compacted expiration heap to bound retained state.
- Unkeyable packets become individual flows without fabricated IP/port values.
- Feature schema version 1.0 with deterministic ordering, rates, protocol one-hot fields, explicit missingness flags, and model-schema compatibility checks.
- `docs/FEATURE_SCHEMA.md` documents all 32 model inputs and their calculations.

### Verification

- `.venv\Scripts\python.exe -m pytest`: PASS, 25 tests across packet, flow, and feature modules.
- `.venv\Scripts\python.exe -m compileall -q nids_engine tests`: PASS.
- `git diff --check`: PASS.
- Tests cover reverse-direction keying, counters, zero duration, idle/active/capacity finalization, out-of-order timestamps, bounded heap growth, non-IP isolation, deterministic feature ordering, missing values, and incompatible/invalid feature vectors.

### Next task

Step 3 is complete on GitHub. The next task is Step 4 (dataset and training pipeline).

## Step 4 of 10 — Dataset preparation and model evaluation

**Status:** Pipeline implemented and verified locally; commit and push are pending. Real dataset evaluation is blocked because no dataset or labels were supplied.

### Delivered

- PCAP-to-flow feature export using the same `FlowBuilder` and feature schema as inference, plus blank label templates so labels are supplied from ground truth.
- Combining per-capture CSVs and generating a provenance manifest with a prepared-data SHA-256 and optional upstream checksums.
- Strict numeric/schema/range/rate validation, missing-label and capture-group checks, exact duplicate removal, and rejection of conflicting labels or unexpected identifier columns.
- Deterministic two-stage `GroupShuffleSplit` with no capture-group overlap and all classes required in each split.
- Class-weighted Logistic Regression and Random Forest comparison; validation macro-F1 selects the model, and the held-out test groups are scored once.
- Saved trusted-project joblib model, provenance/configuration metadata, measured timings, and per-class/test metrics when training is run on a supplied dataset.
- Dataset acquisition instructions cite the official CICIDS2017 source and warn that its 80+ CICFlowMeter features do not directly match this project's schema. No dataset was downloaded.
- Model binaries and generated evaluation files are excluded from Git.
- CSV combination and label export reject destructive output paths; combined CSV output is written atomically so a rejected input does not leave a partial destination.

### Verification

- `.venv\Scripts\python.exe -m pytest`: PASS, 36 tests.
- `.venv\Scripts\python.exe -m compileall -q ml nids_engine tests`: PASS.
- `.venv\Scripts\python.exe -m ml.data.export_features --help`: PASS.
- `.venv\Scripts\python.exe -m ml.data.combine_features --help`: PASS.
- `.venv\Scripts\python.exe -m ml.data.manifest --help`: PASS.
- `.venv\Scripts\python.exe -m ml.training.train --help`: PASS.
- `git diff --check`: PASS.
- Destructive-path and atomic-output regression coverage: PASS.
- Training was exercised only with labeled synthetic test fixtures. Their metrics are not real dataset results and are not included as project evaluation results.
- No dataset/model: BLOCKED pending a provenance-tracked feature CSV with ground-truth labels and at least five independent capture groups.

### Next task

Step 4 commit `fef5845` was pushed to `origin/main`. Next implement trusted model loading, schema compatibility checks, inference output, and explainable detection/alert rules in Step 5.

## Step 5 of 10 — Inference and explainable alerts

**Status:** Implemented, verified, committed as `6b25899`, and pushed to `origin/main`. Real model detections are blocked because no real labeled dataset/model was supplied.

### Delivered

- Project model metadata includes artifact SHA-256 and joblib version. The loader checks its sidecar, checksum, feature schema/order, supported pipeline/classifier type, fitted class names, and scikit-learn/joblib versions before allowing inference.
- Missing, invalid, incompatible, checksum-mismatched, feature-rejected, and inference-error outcomes are explicit. The monitor continues in rule-only mode when a model is absent or unusable.
- Predictions record the class, model version, schema version, UTC time, and status. No confidence/probability is reported because the current estimators are not calibrated.
- Explainable model-class alerts and two review rules: TCP SYN burst and high per-flow packet rate. Alerts include stable codes, severity, endpoints, timestamps, model version where applicable, and threshold evidence.
- Bounded, 60-second process-local duplicate suppression for matching detection/protocol/endpoint signatures.
- `python -m nids_engine.monitor` streams authorized PCAPs through flow processing, optional inference, and alert output as JSON lines.
- `docs/DETECTION.md` documents operation, rules, false-positive limitations, and artifact trust requirements.

### Verification

- `.venv\Scripts\python.exe -m pytest`: PASS, 42 tests.
- `.venv\Scripts\python.exe -m compileall -q ml nids_engine tests`: PASS.
- `.venv\Scripts\python.exe -m nids_engine.monitor --help`: PASS.
- Controlled PCAP monitor replay in rule-only mode: PASS.
- Controlled PCAP-to-model-inference-to-alert run with a synthetic training fixture: PASS; this verifies wiring only, not model quality.
- Synthetic-fixture trained artifact load and prediction, incompatible schema rejection, and checksum mismatch rejection: PASS.
- Packaged `nids-monitor` installation: NOT VERIFIED. The partial `.venv` has no `pip` module; a targeted install attempt hit a sandbox temporary-directory permission error. The verified `python -m nids_engine.monitor` invocation works.
- `git diff --check`: PASS.
- Real model inference and alert quality: BLOCKED until a real labeled dataset and evaluated model are supplied.

### Next task

Step 5 commit `6b25899` was pushed to `origin/main`. Next implement PostgreSQL persistence and a validated REST API in Step 6.

## Step 6 of 10 — Persistence and REST API

**Status:** Implemented and verified locally. PostgreSQL service integration is blocked on this host because no local server is listening on port 5432.

### Delivered

- Added SQLAlchemy 2.1 models for flow records, prediction status/results, and related alerts; timestamps normalize to UTC, capture/flow identity is unique per capture, and indexes support time/protocol/severity/status queries.
- Added Alembic initial migration, environment configuration, and backend dependency/version locks.
- Added an atomic ingestion service. `nids_engine.monitor --database-url <URL>` persists each flow, prediction, and alert set in one transaction and stops if the database write fails.
- Added FastAPI health, paginated flow and alert lists, detail reads, protocol/severity/status/time filters, validated pagination, and consistent 404/422/503 handling.
- API runner binds to `127.0.0.1` by default. The endpoints are read-only and remain unauthenticated until the planned access-control step.
- Added `docs/API.md` and `docs/DATABASE.md` with migration, route, query, and local operation instructions.

### Verification

- `.venv\Scripts\python.exe -m pytest` in the approved execution context: PASS, 48 tests. The restricted Windows runner blocks TestClient's local asyncio socketpair; tests pass outside that restriction.
- `.venv\Scripts\python.exe -m compileall -q backend database ml nids_engine tests`: PASS.
- Alembic SQLite upgrade to `0001_persistence`: PASS; created `flows`, `predictions`, `alerts`, and `alembic_version`.
- Alembic `check`: PASS, no schema drift.
- PostgreSQL offline migration generation: PASS; SQL rendered for all three application tables without connecting to a server.
- API CLI help and migration history: PASS.
- API pagination/filter/time validation, missing records, readiness success/degraded response, transactional persistence/rollback, and monitor-to-database-to-API flow: PASS.
- PostgreSQL service: BLOCKED; no server on localhost:5432 and `psql` is absent. PostgreSQL was not claimed as integration-tested.
- `git diff --check`: PASS.

### Next task

Next add JWT authentication, password hashing, role enforcement, audit events, and authenticated WebSocket delivery in Step 7.
