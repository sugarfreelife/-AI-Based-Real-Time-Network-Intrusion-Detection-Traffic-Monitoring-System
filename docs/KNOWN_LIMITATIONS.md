# Known Limitations and Blockers

This list reflects the Step 1 audit and will be updated with evidence as the project develops.

| Item | Status | Evidence / recovery |
|---|---|---|
| GitHub destination | CONFIGURED | `origin` points to the user-provided repository; Step 1 commit `cad3edf` was pushed to `main`. |
| Project Python libraries | RESOLVED FOR LOCAL STEPS 2–7 | Scapy 2.8.0, NumPy 2.4.5, pandas 3.0.6, scikit-learn 1.9.1, FastAPI 0.158.1, Pydantic 2.14.1, SQLAlchemy 2.1.5, Alembic 1.20.0, Psycopg 3.3.6, Uvicorn 0.54.0, pwdlib 0.3.1, PyJWT 2.15.1, Argon2, and locked dependencies are installed in the ignored project `.venv`. |
| Live packet capture | NOT AVAILABLE / unverified | The Npcap service and libpcap provider were not detected. Offline PCAP/PCAPNG replay works; live capture requires an authorized interface and supported packet-capture driver. |
| Docker services | BLOCKED in this session | Docker CLI is present, but connection to the Docker Desktop Linux engine returned permission denied for its named pipe. |
| PostgreSQL service integration | BLOCKED on this host | `psql` is unavailable and localhost port 5432 refused a connection. Migrations, schema drift, REST behavior, and monitor persistence pass with SQLite. PostgreSQL driver packages are installed; verify against a reachable PostgreSQL service when available. |
| Dataset and trained model | NOT PROVIDED | No dataset or model was present in the empty workspace. No model metrics or supported attack classes can be claimed until data is acquired and evaluated. |
| Full NIDS application | INCOMPLETE | Packet ingestion, flow construction, features, data/training infrastructure, optional inference, alerts, persistence, Argon2id/JWT authentication, role-checked REST, audit events, authenticated WebSocket delivery, and the dashboard are implemented through Step 8. No real model is trained; container deployment and academic handoff remain planned. |
| PostgreSQL authentication integration | BLOCKED on this host | The Step 7 schema migration compiles for PostgreSQL and passes SQLite migration/schema-drift checks. A live PostgreSQL server is unavailable, so connection, row-lock behavior, and production database integration remain untested. |
| Authentication hardening | PARTIAL | Access/refresh lifecycles, role checks, Argon2id, and audit events have local coverage. Login rate limiting, access-token revocation lists, and a security review under a deployed TLS configuration are not implemented. Dashboard tokens are held in memory and require sign-in again after a full page reload. |
| Python environment bootstrap | DEGRADED | `python -m venv` failed during `ensurepip` because the base Python launcher reports that it cannot resolve `C:\Python314\python.exe`. The partial local `.venv` can run the installed project modules, but has no `pip` module. Installing the project entry-point scripts was not verified; a targeted install also hit a permission error in the sandbox temporary directory. |

No packet captures, datasets, credentials, or generated model artifacts should be committed.
