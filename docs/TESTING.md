# Testing

## Current result

Step 1 began with no application code or test suite. The 10-step plan is now complete; the final local Python suite has 60 passing tests, and the dashboard has five passing frontend tests. The Python launcher still emits a location warning, but the project-local Python executable runs the checks.

The Docker CLI is installed, but its engine is inaccessible from this session because access to the Docker Desktop named pipe was denied. A local PostgreSQL service is not available; database/API behavior is checked with SQLite, and PostgreSQL integration remains blocked.

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
| 6 | Full packet/flow/ML/inference/database/API suite | PASS, 48 tests; run in the approved execution context because the restricted runner blocks TestClient's local asyncio socketpair |
| 6 | Alembic SQLite upgrade and schema-drift check | PASS; `0001_persistence`, no new operations detected |
| 6 | PostgreSQL offline migration SQL generation | PASS; DDL rendered without a server connection |
| 6 | REST pagination, filters, validation, and health states | PASS, SQLite TestClient coverage |
| 6 | Monitor-to-database-to-API persistence | PASS, SQLite integration test |
| 6 | PostgreSQL server integration | BLOCKED; no local listener on 5432 and `psql` is unavailable |
| 6 | API CLI help and Alembic history | PASS |
| 7 | Authentication, role permissions, refresh-token lifecycle, and WebSocket behavior | PASS, covered by the 59-test Step 7 suite |
| 8 | Python integration/unit suite | PASS, 60 tests |
| 8 | Dashboard type check, frontend tests, and production build | PASS; 5 frontend tests |
| 8 | Strict UI audit and design contract lint | PASS; 0 audit findings and 0 lint warnings |
| 9 | `docker compose config --quiet` | PASS with throwaway validation-only secrets |
| 9 | `docker compose --profile demo config --quiet` | PASS; the optional monitor service parses |
| 9 | Docker image builds and service startup | BLOCKED; access to the Docker Desktop Linux engine named pipe is denied |
| 9 | PostgreSQL-backed container PCAP demo | NOT TESTED; requires the Docker engine and an authorized capture |
| 10 | Full Python integration suite | PASS, 60 tests via `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-step10-tmp` |
| 10 | Dashboard type check, frontend tests, and production build | PASS; 5 tests; main JS 309.13 kB, chart chunk 357.07 kB, CSS 34.60 kB (pre-gzip) |
| 10 | Fresh SQLite migration through `0002_authentication` and Alembic schema-drift check | PASS; no new upgrade operations detected |
| 10 | Replay, monitor, API, admin provisioning, and training CLI help | PASS; live capture still lacks libpcap support |
| 10 | Credential-shaped tracked-source scan and Git ignore checks | PASS |
| 10 | Docker image build, PostgreSQL server, real-data metrics, and live capture | BLOCKED or NOT TESTED as listed in the final handoff |

The Step 4 training test uses a clearly synthetic fixture to verify software behavior and artifact shape. Its scores are not model results and must not be reported as research performance.

Step 5 also uses a synthetic fixture to verify that a trusted pipeline can be loaded and called. It does not establish model quality on real traffic. Heuristic alerts verify rule behavior only; they are review signals, not proof of compromise.

Step 6 database and API checks use temporary SQLite databases. They validate the ORM, migrations, pagination, filtering, and transaction behavior, but do not establish PostgreSQL server connectivity or operational behavior.

Step 8 browser inspection used a local synthetic-only SQLite review fixture to verify sign-in and populated persisted alert rows. The final browser-level WebSocket indicator was not rechecked after the runtime dependency adjustment; authenticated WebSocket behavior is covered by the backend suite. Fixture data is not a production or research result.

Step 9's Compose configuration check validates the service definition only. It is not evidence that Docker images build, PostgreSQL starts, migrations run in a container, or the dashboard can reach those services. The current host's Docker engine access must be resolved before those checks can be reported as passing.

Step 10's full Python and frontend suites pass. A fresh SQLite database migrated to the latest Alembic revision and `alembic check` found no schema drift. This does not establish live PostgreSQL or Docker behavior. No classifier quality or real traffic performance was measured because no verified dataset/model was available.

Record future maintenance checks here with the exact command, result, and relevant blocker. Keep unit tests separate from infrastructure-dependent checks. Do not report an unrun check as passing.
