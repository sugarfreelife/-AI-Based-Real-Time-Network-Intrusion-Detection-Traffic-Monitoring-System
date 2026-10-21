# Known Limitations and Blockers

This list reflects the Step 1 audit and will be updated with evidence as the project develops.

| Item | Status | Evidence / recovery |
|---|---|---|
| GitHub destination | CONFIGURED | `origin` points to the user-provided repository; Step 1 commit `cad3edf` was pushed to `main`. |
| Scapy and ML/data libraries | PARTIALLY RESOLVED | Scapy 2.8.0 is installed in the ignored project `.venv`; Pandas, NumPy, and scikit-learn remain absent until the ML step. |
| Live packet capture | NOT AVAILABLE / unverified | The Npcap service and libpcap provider were not detected. Offline PCAP/PCAPNG replay works; live capture requires an authorized interface and supported packet-capture driver. |
| Docker services | BLOCKED in this session | Docker CLI is present, but connection to the Docker Desktop Linux engine returned permission denied for its named pipe. |
| PostgreSQL | NOT TESTED | `psql` is unavailable and server availability is unknown. Database integration remains unverified until a reachable PostgreSQL service exists. |
| Dataset and trained model | NOT PROVIDED | No dataset or model was present in the empty workspace. No model metrics or supported attack classes can be claimed until data is acquired and evaluated. |
| Full NIDS application | INCOMPLETE | Packet ingestion and replay are implemented in Step 2. Flow construction, features, ML, database, API, authentication, WebSockets, and dashboard work remain planned. |
| Python environment bootstrap | DEGRADED | `python -m venv` failed during `ensurepip` because the base Python launcher reports that it cannot resolve `C:\Python314\python.exe`. The local `.venv` executable can run after pinned packages were installed into its site-packages. |

No packet captures, datasets, credentials, or generated model artifacts should be committed.
