# Known Limitations and Blockers

This list reflects the Step 1 audit and will be updated with evidence as the project develops.

| Item | Status | Evidence / recovery |
|---|---|---|
| GitHub destination | BLOCKED | No remote exists and GitHub CLI is unavailable. Supply the repository URL; then configure the remote and push each completed step commit. |
| Scapy and ML/data libraries | BLOCKED for those components | Scapy, Pandas, NumPy, and scikit-learn were not detected in the current Python environment. Add pinned project dependencies in the relevant implementation step. |
| Live packet capture | NOT AVAILABLE / unverified | Scapy and the Npcap service were not detected. Use offline PCAP replay first; live capture requires an authorized interface and supported packet-capture driver. |
| Docker services | BLOCKED in this session | Docker CLI is present, but connection to the Docker Desktop Linux engine returned permission denied for its named pipe. |
| PostgreSQL | NOT TESTED | `psql` is unavailable and server availability is unknown. Database integration remains unverified until a reachable PostgreSQL service exists. |
| Dataset and trained model | NOT PROVIDED | No dataset or model was present in the empty workspace. No model metrics or supported attack classes can be claimed until data is acquired and evaluated. |
| Application functionality | NOT IMPLEMENTED | This is a fresh, empty workspace. Step 1 creates the foundation only. |

No packet captures, datasets, credentials, or generated model artifacts should be committed.
