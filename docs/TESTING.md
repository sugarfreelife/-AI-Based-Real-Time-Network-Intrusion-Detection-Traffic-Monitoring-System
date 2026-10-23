# Testing

## Current result

Step 1 began with no application code or test suite. The original 10-step plan and extension through Step 20 are complete; Step 10's 60-Python-test/five-frontend-test result is a historical baseline. The host Python launcher now fails to locate its configured Python installation, so current backend suites run in the project container with the workspace mounted read-only; frontend checks run with the locked Node dependencies.

The initial Step 10 audit could not access Docker due to named-pipe permissions. On 2026-10-22, elevated local execution succeeded: Compose images built, PostgreSQL/API became healthy, migrations ran through `0002_authentication`, and the dashboard and database readiness endpoint returned HTTP 200. The exact runtime follow-up is recorded below. No authorized PCAP or labeled research dataset was supplied.

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
| 10 | Docker image build, PostgreSQL server, real-data metrics, and live capture | At original Step 10 handoff: infrastructure access blocked; research data/live capture unavailable |

## Post-Step 10 runtime verification — 2026-10-22

This follow-up updates the infrastructure checks without adding an implementation step. The ten-step plan remains complete.

| Check | Result | Evidence |
|---|---|---|
| `docker compose up --build --detach` | PASS | API and dashboard images built; PostgreSQL, API, and dashboard containers started. |
| `docker compose ps --format json` | PASS | PostgreSQL and API healthy; dashboard running. |
| `docker compose exec -T api python -m alembic current` | PASS | PostgreSQL migration state is `0002_authentication (head)`. |
| `GET http://127.0.0.1:8080/` | PASS | HTTP 200; app root element present. |
| `GET http://127.0.0.1:8080/health/ready` | PASS | HTTP 200; `{"status":"ready","database":"available"}`. |
| PostgreSQL-backed account/replay flow | NOT TESTED | No account was provisioned and no authorized capture was supplied. |
| Real-data model evaluation and live capture | BLOCKED / NOT TESTED | No verified labeled dataset/model or supported live-capture provider is available. |
| Step 11 isolated PostgreSQL integration test | PASS, 1 test in 8.83 seconds, no warnings | Covered authentication, flow/prediction/alert persistence, acknowledgement, refresh rotation, WebSocket delivery, and cleanup. The disposable `nids-step11` project and volume were removed. |
| Step 12 monitor/capture-run regression checks | PASS, 20 tests | SQLite success/failure/partial-run lifecycle and existing backend persistence coverage. |
| Step 12 fresh SQLite migration and schema drift | PASS | Reached `0003_capture_runs (head)`; `alembic check` reported no new upgrade operations. |
| Step 12 PostgreSQL migration and integration | PASS, 3 tests | Disposable PostgreSQL applied `0003_capture_runs`; PostgreSQL end-to-end and capture-run lifecycle tests passed, then the test volume was removed. |
| Step 13 retry-safe persistence and monitor replay | PASS, 22 focused tests | Same-ID replay creates no duplicate flow/prediction/alert rows, increments retry counters, retains acknowledgement state, and rejects conflicting flow data. |
| Step 13 full Python suite | PASS, 64 passed, 1 opt-in PostgreSQL test skipped | The PostgreSQL test was run separately against a disposable database and passed. |
| Step 13 bytecode compilation | PASS | Compiled backend, migration, ML, packet engine, and test modules; cache files were directed to temporary storage. |
| Step 13 fresh SQLite migration and schema drift | PASS | Reached `0004_retry_safe_replay (head)`; Alembic detected no new operations. |
| Step 13 PostgreSQL idempotency integration | PASS, 1 test | Disposable PostgreSQL applied `0004_retry_safe_replay`; duplicate persistence returned the original record, then the `nids-step13` project and volume were removed. |
| Step 14 capture history API | PASS, 20 backend tests | Authenticated list/detail, pagination, status/time filters, empty results, validation, 404, and role-based read access passed with SQLite. |
| Step 14 PostgreSQL capture history | PASS, 1 integration test | Authenticated capture list/detail ran against disposable PostgreSQL; the `nids-step14` project and volume were removed. |
| Step 15 analytics summary and timeline | PASS, 2 focused tests | SQLite coverage confirms persisted counts, severity/protocol/status breakdowns, UTC ranges, zero-filled hour/day buckets, empty data, input validation, range limits, and authentication. |
| Step 15 PostgreSQL analytics aggregation | PASS, 1 integration test | PostgreSQL summary and UTC time-bucket SQL returned expected persisted counts; the `nids-step15` project and volume were removed. |
| Step 16 dashboard regressions | PASS, 10 frontend tests | Three existing tests and five new dashboard tests cover persisted aggregate rendering, accessible timeline values, URL-backed intervals, capture details and status filters, pagination/offsets, and retryable errors. `npm run typecheck` and `npm run build` pass. |
| Step 17 model status and evaluation | PASS | 12 frontend tests across 3 files; API tests cover authenticated not-configured and configured-missing states; training tests verify report SHA-256 binding, valid held-out display, and suppression of a changed report. Strict type-check/build and the premium UI audit pass. The production bundle is 698.42 kB before gzip and is slated for Step 20 code splitting. |
| Step 18 administrator user management | PASS | 24 SQLite backend tests; 2 isolated PostgreSQL integration tests; 15 frontend tests. Coverage includes admin-only listing, activation, last-admin and self-deactivation guards, audit privacy, immediate access blocking, refresh-session revocation, account creation, and permission errors. At Step 18 the initial bundle was 709.18 kB; Step 20 later split route/chart code. |
| Step 19 login abuse controls | PASS | 28 backend tests pass. Coverage includes configured limits and startup bounds, same-peer throttling despite changing `X-Forwarded-For`, `429` plus `Retry-After`, one audit entry per blocked window without credentials/client address, successful-login reset, lockout/window expiry, bounded overflow behavior, and launcher proxy-header disabling. Compose config validates. |
| Step 20 final software suite | PASS, 74 passed / 2 opt-in PostgreSQL cases skipped | Step 18 separately ran both PostgreSQL integration tests successfully; the Step 20 isolated Compose demo also migrated a fresh database and persisted 192 generated packets into 8 flows and 8 rule alerts before removing its volume. |
| Step 20 dashboard | PASS, 15 frontend tests | TypeScript production build passed. Route splitting reduced the initial JavaScript chunk to 267.48 kB; the 337.60 kB chart chunk is also under the 500 kB warning threshold. API, monitor, and dashboard container images built. |
| Step 20 measured replay | PASS, synthetic software fixture only | 2,400 packets per run, five runs; median 23.765572 s end to end, 100.99 packets/s, and 9.9023 ms per input packet in CPython 3.12.15/Linux WSL2 container. Not real network or detection performance. |

The opt-in PostgreSQL integration test is `tests/test_postgres_integration.py`. It refuses to run unless explicitly enabled and the database name contains `test`. It uses only uniquely named rows and removes them after the run. To exercise it against an isolated Compose project:

```powershell
$env:POSTGRES_DB = "nids_test"
docker compose -p nids-step11 up --detach --wait postgres api
docker compose -p nids-step11 run --rm --no-deps -e NIDS_ENABLE_POSTGRES_TESTS=1 --volume .\tests:/workspace/tests:ro api python -m pytest -c /app/pyproject.toml -p no:cacheprovider --basetemp /tmp/pytest-step11 -q /workspace/tests/test_postgres_integration.py -m postgres
docker compose -p nids-step11 down --volumes
Remove-Item Env:\POSTGRES_DB
```

Use `.env` from the repository root for Compose secrets. The isolated project name and `nids_test` database prevent the test from touching the normal `nids-local` database. The command above is a disposable verification workflow; do not replace the project name with `nids-local`.

The Step 4 training test uses a clearly synthetic fixture to verify software behavior and artifact shape. Its scores are not model results and must not be reported as research performance.

Step 5 also uses a synthetic fixture to verify that a trusted pipeline can be loaded and called. It does not establish model quality on real traffic. Heuristic alerts verify rule behavior only; they are review signals, not proof of compromise.

Step 6 database and API checks use temporary SQLite databases. They validate the ORM, migrations, pagination, filtering, and transaction behavior, but do not establish PostgreSQL server connectivity or operational behavior.

Step 8 browser inspection used a local synthetic-only SQLite review fixture to verify sign-in and populated persisted alert rows. The final browser-level WebSocket indicator was not rechecked after the runtime dependency adjustment; authenticated WebSocket behavior is covered by the backend suite. Fixture data is not a production or research result.

At Step 9, the Compose configuration check validated the service definition only because Docker engine access was denied. That historical limitation was resolved for local deployment on 2026-10-22, as recorded above.

Step 10's full Python and frontend suites pass. A fresh SQLite database migrated to the latest Alembic revision and `alembic check` found no schema drift. The subsequent Compose verification covers PostgreSQL startup/migrations, API readiness, and dashboard serving; it does not cover the full PostgreSQL auth/replay path. No classifier quality or real traffic performance was measured because no verified dataset/model was available.

Record future maintenance checks here with the exact command, result, and relevant blocker. Keep unit tests separate from infrastructure-dependent checks. Do not report an unrun check as passing.
