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

**Status:** Implemented and verified locally; commit and push are pending.

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

Add documented dataset handling and a reproducible training/evaluation pipeline in Step 4. Do not report model metrics until a real, provenance-tracked dataset is supplied and evaluated.
