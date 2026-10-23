# Known Limitations and Blockers

This list reflects all 20 implementation steps and the runtime verification available through 2026-10-23. It separates completed software behavior from unavailable data and environment-dependent claims.

| Item | Status | Evidence / recovery |
|---|---|---|
| GitHub destination | CONFIGURED | `origin` points to the user-provided repository; Step 1 commit `cad3edf` was pushed to `main`. |
| Project dependencies | AVAILABLE IN PROJECT CONTAINER | Dependencies are pinned in lock files and installed in the Docker image. The host `.venv` points to a missing Python installation and could not run; current Python checks used the container. |
| Live packet capture | NOT AVAILABLE / unverified | The Npcap service and libpcap provider were not detected. Offline PCAP/PCAPNG replay works; live capture requires an authorized interface and supported packet-capture driver. |
| Docker services | CONFIGURATION AND FINAL IMAGES VERIFIED | Compose configuration passes; current API, monitor, and dashboard images built. An isolated Step 20 PostgreSQL/API/monitor demonstration completed and cleaned up its database volume. The existing local `nids-local` stack was left untouched. |
| PostgreSQL service integration | VERIFIED WITH DISPOSABLE TEST DATABASES | Isolated coverage includes auth, refresh rotation, persisted alerts/WebSockets, capture history, analytics, admin account/session protections, and a Compose monitor replay. Each disposable project and volume was removed. |
| Dataset and trained model | NOT PROVIDED | No dataset or model was present in the empty workspace. No model metrics or supported attack classes can be claimed until data is acquired and evaluated. |
| Full NIDS application | IMPLEMENTATION COMPLETE | All 20 planned steps are implemented and individually pushed. First administrator provisioning and authorized PCAP replay remain operator actions. No real model is trained. |
| PostgreSQL authentication and persistence integration | PARTIALLY VERIFIED | Isolated PostgreSQL integration tests cover login, refresh rotation, role-protected actions, administrator account deactivation/session revocation, last-admin protection, persisted alerts, WebSockets, captures, and analytics. Local Compose verifies startup, migrations, and readiness. Containerized monitor replay was not tested because no authorized PCAP was supplied. |
| Authentication hardening | PARTIAL | Access/refresh lifecycles, role checks, Argon2id, account deactivation/session revocation, audit events, and process-local bounded login throttling have local coverage. Distributed rate limiting, access-token revocation lists, and a security review under a deployed TLS configuration are not implemented. Forwarded client-address headers are ignored, so clients behind a proxy share the proxy's address bucket for a given username. Dashboard tokens are held in memory and require sign-in again after a full page reload. |
| Synthetic replay performance | MEASURED; SOFTWARE FIXTURE ONLY | A controlled 2,400-packet run measured a 100.99 packets/second median in the isolated Linux/WSL2 container. This includes process startup and JSON output; it is not live network capacity, tail latency, or detection-quality evidence. |
| Python environment bootstrap | DEGRADED | The host `.venv` fails because its configured interpreter `C:\Python314\python.exe` is missing. The full Python suite and benchmark ran in the Docker image; install/repair the host Python runtime before using host-side Python commands. |

No packet captures, datasets, credentials, or generated model artifacts should be committed.
