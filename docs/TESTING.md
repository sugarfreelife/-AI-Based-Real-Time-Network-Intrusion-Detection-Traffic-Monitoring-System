# Testing

## Current result

Step 1 began with no application code or test suite. Steps 2–4 add packet, flow, feature, and dataset/training tests. The Python launcher still emits a location warning, but the project-local Python executable runs the checks.

The Docker CLI is installed, but its engine is inaccessible from this session because access to the Docker Desktop named pipe was denied. PostgreSQL integration checks are therefore not yet available.

## Verification record

| Step | Check | Result |
|---|---|---|
| 1 | Repository and runtime audit | PASS, findings recorded in `docs/PROGRESS.md` |
| 1 | Application test suite | NOT TESTED; no application code or tests existed |
| 1 | Docker engine | BLOCKED; named-pipe permission denied |
| 1 | PostgreSQL connection | NOT TESTED; server availability not established |
| 2 | Packet parser and PCAP/PCAPNG replay | PASS, 12 tests via `.venv\Scripts\python.exe -m pytest` |
| 2 | Python bytecode compilation | PASS via `.venv\Scripts\python.exe -m compileall -q nids_engine tests` |
| 2 | CLI help and controlled fresh-process replay | PASS |
| 2 | Live capture | NOT TESTED; Npcap/libpcap support unavailable |
| 3 | Flow and feature unit suite | PASS, 25 total tests via `.venv\Scripts\python.exe -m pytest` |
| 3 | Python bytecode compilation | PASS via `.venv\Scripts\python.exe -m compileall -q nids_engine tests` |
| 3 | Patch whitespace check | PASS via `git diff --check` |
| 4 | Full packet/flow/feature/dataset/training unit suite | PASS, 36 tests via `.venv\Scripts\python.exe -m pytest` |
| 4 | Python bytecode compilation | PASS via `.venv\Scripts\python.exe -m compileall -q ml nids_engine tests` |
| 4 | Export, combine, manifest, and training CLI help | PASS |
| 4 | CSV overwrite/partial-output protections | PASS, regression test |
| 4 | Real dataset model evaluation | BLOCKED; no real dataset or verified labels were supplied |
| 5 | Full packet/flow/feature/dataset/inference/alert unit suite | PASS, 42 tests via `.venv\Scripts\python.exe -m pytest` |
| 5 | Python bytecode compilation | PASS via `.venv\Scripts\python.exe -m compileall -q ml nids_engine tests` |
| 5 | PCAP monitor CLI help and rule-only PCAP replay | PASS |
| 5 | Synthetic model PCAP-to-inference-to-alert integration | PASS |
| 5 | Trusted model load and synthetic-fixture prediction | PASS; software test only, not research evaluation |
| 5 | Missing, incompatible, and checksum-mismatched model states | PASS; invalid artifacts are not deserialized |
| 5 | Real model inference and real labeled traffic alerts | BLOCKED; no verified labeled dataset or trained artifact is available |
| 5 | Installed `nids-monitor` console script | NOT VERIFIED; the partial `.venv` has no `pip` module and the targeted install hit a sandbox temporary-directory permission error; `python -m nids_engine.monitor` is verified |

The Step 4 training test uses a clearly synthetic fixture to verify software behavior and artifact shape. Its scores are not model results and must not be reported as research performance.

Step 5 also uses a synthetic fixture to verify that a trusted pipeline can be loaded and called. It does not establish model quality on real traffic. Heuristic alerts verify rule behavior only; they are review signals, not proof of compromise.

Later steps must record the exact command, result, and relevant blocker here. Keep unit tests separate from infrastructure-dependent checks. Do not report an unrun check as passing.
