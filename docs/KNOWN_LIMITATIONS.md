# Known Limitations and Blockers

This list reflects Steps 1–18 and the runtime verification available through 2026-10-23. It separates implemented software from unavailable data and remaining validation.

| Item | Status | Evidence / recovery |
|---|---|---|
| GitHub destination | CONFIGURED | `origin` points to the user-provided repository; Step 1 commit `cad3edf` was pushed to `main`. |
| Project Python libraries | RESOLVED FOR LOCAL STEPS 2–10 | Scapy 2.8.0, NumPy 2.4.5, pandas 3.0.6, scikit-learn 1.9.1, FastAPI 0.158.1, Pydantic 2.14.1, SQLAlchemy 2.1.5, Alembic 1.20.0, Psycopg 3.3.6, Uvicorn 0.54.0, websockets 17.2, pwdlib 0.3.1, PyJWT 2.15.1, Argon2, and locked dependencies are installed in the ignored project `.venv`. |
| Live packet capture | NOT AVAILABLE / unverified | The Npcap service and libpcap provider were not detected. Offline PCAP/PCAPNG replay works; live capture requires an authorized interface and supported packet-capture driver. |
| Docker services | VERIFIED LOCALLY | Compose images built; PostgreSQL and API are healthy; dashboard is serving on `http://127.0.0.1:8080`. See `HANDOFF.md` for exact checks. |
| PostgreSQL service integration | VERIFIED WITH DISPOSABLE TEST DATABASES | Step 11 covers auth, persistence, acknowledgement, refresh rotation, and authenticated WebSocket delivery; Steps 12–15 cover lifecycle, retry identity, capture history, and analytics using isolated databases. The persistent local Compose stack was separately verified through `0002_authentication`. |
| Dataset and trained model | NOT PROVIDED | No dataset or model was present in the empty workspace. No model metrics or supported attack classes can be claimed until data is acquired and evaluated. |
| Full NIDS application | IN PROGRESS; LOCAL DEPLOYMENT VERIFIED | Steps 1–18 are implemented, including overview analytics, capture history, truthful model/evaluation state, and audited administrator account controls. Steps 19–20 remain. First administrator provisioning and authorized PCAP replay remain operator actions. No real model is trained. |
| PostgreSQL authentication and persistence integration | PARTIALLY VERIFIED | Isolated PostgreSQL integration tests cover login, refresh rotation, role-protected actions, administrator account deactivation/session revocation, last-admin protection, persisted alerts, WebSockets, captures, and analytics. Local Compose verifies startup, migrations, and readiness. Containerized monitor replay was not tested because no authorized PCAP was supplied. |
| Authentication hardening | PARTIAL | Access/refresh lifecycles, role checks, Argon2id, account deactivation/session revocation, and audit events have local coverage. Bounded login rate limiting is Step 19; access-token revocation lists and a security review under a deployed TLS configuration are not implemented. Dashboard tokens are held in memory and require sign-in again after a full page reload. |
| Python environment bootstrap | DEGRADED | `python -m venv` failed during `ensurepip` because the base Python launcher reports that it cannot resolve `C:\Python314\python.exe`. The partial local `.venv` can run the installed project modules, but has no `pip` module. Installing the project entry-point scripts was not verified; a targeted install also hit a permission error in the sandbox temporary directory. |

No packet captures, datasets, credentials, or generated model artifacts should be committed.
