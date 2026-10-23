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

**Status:** Implemented, verified, committed as `fef5845`, and pushed to `origin/main`. Real dataset evaluation is blocked because no dataset or labels were supplied.

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

**Status:** Implemented and verified, committed as `f4ac18b`, and pushed to `origin/main`. PostgreSQL service integration is blocked on this host because no local server is listening on port 5432.

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

## Step 7 of 10 — WebSockets and access control

**Status:** Implemented and verified; the Step 7 checkpoint is committed and pushed to `origin/main` before Step 8.

### Delivered

- Added users with normalized unique usernames, active state, admin/analyst/viewer roles, Argon2id password hashes via `pwdlib`, and a hidden-input command for the first administrator. Public registration is not exposed.
- Added HS256 access and refresh JWTs with issuer/audience validation, required claims, token-purpose checks, and a 15-minute access lifetime. Refresh tokens last 14 days, rotate on use, and are stored only as SHA-256 digests of their `jti` values. Reuse of a rotated token revokes all active refresh sessions for that user.
- Protected flow and alert REST reads, provided `/auth/me`, and added admin-only user creation. Admins and analysts can acknowledge an alert; viewer actions are rejected. Alert actor and timestamp are persisted.
- Added audit records for bootstrap/user creation, successful and failed login, refresh, logout, role denials, refresh reuse, and alert acknowledgement. Audit details do not contain passwords or tokens.
- Added `/api/v1/ws/alerts`. The first WebSocket frame carries an access token; URLs do not carry tokens. New alerts are polled from persistence, including alerts created by the separate monitor process. Clients can resume with the last alert timestamp and ID; expired/invalid authentication and database failures close the connection with documented codes.
- Added Alembic migration `0002_authentication`, locked `pwdlib`, Argon2, and PyJWT dependencies, and updated API, architecture, database, setup, and limitation documents.

### Verification

- `.venv\Scripts\python.exe -m pytest` in the approved execution context: PASS, 59 tests. Added coverage for Argon2id, login/audit behavior, missing secrets, refresh rotation/reuse/logout, role restrictions and denial audit, initial admin provisioning, acknowledgement metadata, authenticated WebSocket delivery, reconnect cursor behavior, and database failure closure.
- `.venv\Scripts\python.exe -m compileall -q backend database/migrations ml nids_engine tests`: PASS.
- Alembic upgrade to `0002_authentication` on fresh SQLite database: PASS. Alembic `check`: PASS, no schema drift.
- PostgreSQL offline migration rendering: PASS; SQL includes user/session/audit tables and acknowledgement columns/FK. A live PostgreSQL service remains unavailable, so PostgreSQL integration is not claimed.
- API runner and admin-provisioning module help: PASS.
- `git diff --check`: PASS.
- Docker deployment, dashboard, login rate limiting, and deployed TLS review remain pending or untested in later steps.

### Next task

Step 7 is complete on GitHub. Next implement the authenticated dashboard in Step 8.

## Step 8 of 10 — Authenticated dashboard

**Status:** Implemented, verified, committed as `d6076f6`, and pushed to `origin/main`.

### Delivered

- Added a strict TypeScript React dashboard with sign-in, alerts, and flows screens backed by the authenticated API. Access and refresh tokens stay in memory; refresh rotation, sign-out, role-based navigation, and viewer restrictions are handled in the client.
- Added URL-backed filters, pagination, detail inspection, status/severity views, and alert acknowledgement for analysts/admins. The severity chart describes only the currently loaded page; the dashboard does not invent totals or production telemetry.
- Added explicit loading, empty, error, permission, reconnecting, and API health states, responsive navigation, and keyboard-accessible form and table controls.
- Added an exact-origin CORS allowlist for separately hosted development clients. Added `websockets==17.2` to the backend dependency inputs and locks so the pinned Uvicorn runtime includes a WebSocket implementation.
- Added the frontend build, type-check, and test setup; design and UX contracts; strict UI audit report; and setup/API/architecture/limitation documentation.

### Verification

- `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-step8-tmp`: PASS, 60 tests, including CORS, authenticated WebSocket, alert acknowledgement, and API integration coverage.
- In `frontend/`, `npm run typecheck`: PASS; `npm test -- --reporter=dot`: PASS, 5 tests; `npm run build`: PASS. Production output is split into the app and chart chunks without a bundle-size warning.
- Strict UI audit: PASS, 0 findings in `docs/ui-audit-step8.json`.
- `npx --yes --package=@google/design.md designmd lint ..\DESIGN.md`: PASS, 0 warnings.
- `git diff --check`: PASS.
- Browser review with a local synthetic-only SQLite fixture confirmed sign-in and persisted alert rows. The live WebSocket indicator was not rechecked in the browser after adding the backend WebSocket runtime dependency; the authenticated WebSocket behavior is covered by the passing backend suite. The fixture is local, ignored by Git, and contains no production or research metrics.
- Real dataset/model evaluation and PostgreSQL service integration remain blocked as recorded above; Step 8 does not claim either.

### Next task

Step 8 is complete on GitHub. Step 9 covers reproducible operation and documentation.

## Step 9 of 10 — Reproducible operation and academic handoff

**Status:** Implemented, locally validated, committed, and pushed to `origin/main`. Container runtime verification is blocked because this host cannot access the Docker Desktop engine.

### Delivered

- Added a Compose stack with PostgreSQL 17, an API service that waits for database health and applies migrations, a loopback-only dashboard with REST/health/WebSocket reverse proxying, and an optional one-shot PCAP monitor profile.
- Added version-specific Python, Node, Nginx, and PostgreSQL image tags, lock-file installs, health checks, persistent database storage, a non-root API user, and a `.dockerignore` that excludes secrets, local captures, datasets, and model artifacts from image build context.
- Added `.env.example` variables and instructions for local secrets, service startup, first-admin provisioning, authorized PCAP replay, and optional trusted-model use.
- Added `docs/DEPLOYMENT.md`, `docs/VIVA_GUIDE.md`, and `docs/REPORT_OUTLINE.md`. The report outline explicitly separates measured results, software fixture checks, blocked work, and untested claims.
- Updated the README, known limitations, and testing record. Existing API, database, detection, feature schema, and ML methodology documentation remains linked from the deployment and project guides.

### Verification

- `docker compose config --quiet` with throwaway validation-only secret values: PASS.
- `docker compose --profile demo config --quiet` with throwaway validation-only secret values: PASS; the optional monitor profile parses.
- Compose service listing includes PostgreSQL, API, dashboard, and the optional monitor. No validation-only secret was written to a file or printed.
- `git diff --check`: PASS.
- `docker info --format '{{.ServerVersion}}'`: BLOCKED; Docker Desktop engine access returned permission denied for `dockerDesktopLinuxEngine`.
- Image builds, service startup, container migration execution, Nginx runtime configuration, PostgreSQL integration, and the container PCAP replay: NOT TESTED because the engine is inaccessible. Configuration parsing is not reported as runtime verification.
- No default/sample observations are loaded. An empty dashboard remains the expected state until a user provisions an account and replays an authorized capture.

### Next task

Step 9 is complete on GitHub. Step 10 is the final integration and evidence-based handoff.

## Step 10 of 10 — Integration and handoff

**Status:** Complete and pushed to `origin/main`; results are limited to checks that this host can run.

### Delivered

- Re-ran the Python integration suite, dashboard type-check/tests/build, fresh SQLite migration and schema-drift check, and documented command help paths.
- Checked GitHub branch synchronization, Git exclusions for local secrets/captures/datasets/models/databases, and tracked-source strings matching common credential formats.
- Added `docs/HANDOFF.md` with verified capabilities, exact evidence, environmental blockers, and the boundaries on any research claims. The report outline and viva guide remain available as separate academic materials.
- Updated README, limitations, progress, and test records to state that all ten implementation steps are complete while retaining the unresolved infrastructure/data limits.

### Final verification matrix

| Area | Result | Evidence and limits |
|---|---|---|
| Packet, flow, feature, dataset, inference, persistence, REST, auth, and WebSocket software | PASS | 60 Python tests; this is software behavior coverage, not detection-quality evidence. |
| Frontend | PASS | Type-check, 5 tests, and production build; main JavaScript 309.13 kB, chart chunk 357.07 kB, CSS 34.60 kB before gzip. |
| SQLite schema | PASS | Fresh migration reaches `0002_authentication`; Alembic check reports no new operations. |
| Command entry points | PASS | Replay, monitor, API, admin provisioning, and training help commands run. No libpcap provider is available for live capture. |
| Compose definitions | PASS | Base stack and `demo` profile both pass `docker compose config --quiet` with transient validation-only secrets. |
| Docker image build and service execution | PASS in post-Step-10 runtime follow-up | Compose images built; PostgreSQL/API became healthy; dashboard is running. |
| PostgreSQL startup, migrations, and API readiness | PASS in post-Step-10 runtime follow-up | Migration `0002_authentication (head)` and readiness response reports database available. Full auth/replay flow remains untested against PostgreSQL. |
| Real-data model training and detection metrics | BLOCKED | No provenance-tracked labeled data or model was supplied. No model scores or research metrics are reported. |
| Live packet capture | NOT TESTED | Npcap/libpcap is unavailable on this host; only offline replay is covered. |
| Tracked-secret scan and Git exclusions | PASS | No credential-shaped strings found in tracked source; `.env`, PCAPs, local data/model artifacts, databases, and frontend dependencies are ignored. |
| GitHub checkpoint | PASS | `main` matches `origin/main`; the Step 10 commit is the final planned checkpoint. |

### Next action

The ten-step build is finished. The later runtime follow-up resolved the local Docker/PostgreSQL deployment checks. Further research evaluation depends on provenance-tracked labeled captures; account provisioning, authorized capture replay, and security review remain operator/environment-dependent tasks. No additional implementation step is planned.

## Runtime verification follow-up after Step 10 — 2026-10-22

This deployment check was completed after the ten planned steps. It updates infrastructure evidence and does not add an implementation step.

### Verification

- Created a local `.env` with generated secrets. The file is ignored by Git; secret values were not printed or committed.
- `docker compose up --build --detach`: PASS. Python and frontend images built, PostgreSQL started, migrations ran, and the API/dashboard started.
- `docker compose ps --format json`: PostgreSQL and API report healthy; dashboard is running.
- `docker compose exec -T api python -m alembic current`: PASS, PostgreSQL is at `0002_authentication (head)`.
- `GET http://127.0.0.1:8080/`: PASS, HTTP 200 with the application root element.
- `GET http://127.0.0.1:8080/health/ready`: PASS, HTTP 200 with `{"status":"ready","database":"available"}`.
- The local Compose stack remains running with its persistent PostgreSQL volume. No administrator was provisioned; use the documented hidden-password command before sign-in.
- No PCAP was replayed. No real dataset/model was present; detection-quality metrics remain unavailable and unclaimed.

## Step 11 of 20 — PostgreSQL integration coverage

**Status:** Implemented and verified against a disposable PostgreSQL Compose project; the test database and volume were removed after the run.

### Delivered

- Added opt-in PostgreSQL integration coverage for login, authenticated reads, transactional flow/alert persistence, acknowledgement, refresh rotation, and WebSocket authentication.
- The test refuses to connect unless explicitly enabled and the target database name contains `test`; generated database rows are uniquely scoped and cleaned up.
- Extended the plan to Steps 11–20 with individual commit/push checkpoints as requested.

### Verification

- `docker compose -p nids-step11 up --build --detach --wait postgres api`: PASS; the temporary PostgreSQL service and migrated API became healthy.
- The opt-in integration test: PASS, 1 test in 8.83 seconds with no warnings. It covered login, authenticated `/me` and flows reads, PostgreSQL flow/prediction/alert persistence, acknowledgement, refresh rotation, authenticated WebSocket handshake and alert delivery, and cleanup.
- `docker compose -p nids-step11 down --volumes`: PASS; only the isolated test project containers, network, and database volume were removed. The active `nids-local` project was not touched.

## Step 12 of 20 — Capture-run lifecycle

**Status:** Implemented and verified with SQLite and a disposable PostgreSQL project.

### Delivered

- Added Alembic revision `0003_capture_runs` and a capture-run record for source filename, lifecycle status/timestamps, packet parsing/read counts, flow/prediction/alert counts, model status, elapsed time, and bounded failure code.
- Updated database-backed PCAP replay to create a `running` record, then finalize it as `completed`, `partial`, or `failed`. The stored source is only the filename, not the local path.
- Preserved the existing monitor failure response contract when the database schema is missing.

### Verification

- Focused monitor/backend suite: PASS, 20 tests.
- Fresh SQLite Alembic upgrade and drift check: PASS, `0003_capture_runs (head)`, no new upgrade operations detected.
- Disposable PostgreSQL migration and integration check: PASS, 3 tests; temporary project and volume removed.
- On a forced process termination, a run can remain `running`; this is surfaced as an incomplete state rather than changed to success.

## Step 13 of 20 — Retry-safe replay identity

**Status:** Implemented and verified; ready for its GitHub checkpoint.

### Delivered

- Added `--capture-id` for stable UUIDs, with generated UUIDs remaining the default. The Docker demo accepts the same value through `CAPTURE_ID`.
- Made persistence idempotent for each `(capture_id, flow_id)`. Identical flow and prediction data are skipped, alert IDs may differ across attempts, and acknowledgement state is retained.
- Rejects flow, prediction, alert, source-name, or model-identity conflicts for an existing capture ID without replacing saved observations.
- Added migration `0004_retry_safe_replay` to count attempts and duplicate flows in each capture-run record.

### Verification

- Focused monitor/backend suite: PASS, 22 tests. Includes same-ID PCAP replay, duplicate counters, alert acknowledgement preservation, conflicting flow data rejection, and invalid UUID handling.
- Full Python suite: PASS, 64 tests; the opt-in PostgreSQL integration is run separately below. Bytecode compilation: PASS.
- Fresh SQLite migration and schema check: PASS, `0004_retry_safe_replay (head)`, no new upgrade operations detected.
- Disposable PostgreSQL migration and integration: PASS, 1 test. The migration was applied, retry persistence was exercised, and the isolated project and volume were removed.
