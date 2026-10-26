# Project Context

This file is a short orientation for the person or coding agent who continues this repository. **Updated: 26 October 2026.**

## Current situation

- All planned implementation work through Step 20 is complete.
- Step 21 adds the graphite/brass dashboard and authenticated `/simulation` page. The bounded server-side demo sends 24 synthetic TCP SYN packets through the real parser, flow builder, inference availability check, and alert rules; it produces one `tcp_syn_burst` alert at threshold 20 and does not persist records.
- Git branch: `main`. The last implementation commit is `388ae15`; at the start of this report task the branch was clean and synced with `origin/main`.
- Local Compose stack: `nids-local`. PostgreSQL, API, and dashboard started successfully and reported healthy.
- Dashboard: <http://localhost:8080>. The user's current browser route is `/alerts`.
- A local `admin` account was created because the database did not contain an administrator. Its generated password is in this conversation only; never add it to a tracked file or commit.
- Do not remove the persistent database volume. The app was started against the existing `nids-local` volume, and older local data must be preserved.

## What it is

An authenticated dashboard and backend for authorized offline network-capture analysis. The monitor parses packet metadata, forms bidirectional flows, creates versioned features, applies explainable rules, optionally runs a verified model, and persists the results to PostgreSQL. The dashboard reads those persisted records; it does not collect traffic on its own.

The user is currently viewing Alerts. To understand other screens, use the dashboard navigation: Overview, Capture history, Flows, Model & evaluation, and (for admins) Users.

## Recent operational action

On 26 October 2026, `docker compose up --build --detach --wait` rebuilt the local API/dashboard images and started the stack. PostgreSQL, API, and dashboard reported healthy. The initial-admin CLI was used after a read-only check found no existing admin. No new capture was replayed into the persistent local database during that startup. The Step 20 synthetic smoke replay was performed earlier against a disposable database, which was removed after verification.

## Evidence and limitations

- Final Step 20 checks: Python **74 passed / 2 skipped**, frontend **15 passed**, production build passed, Compose images built, isolated demo persisted 192 packets into 8 flows and 8 heuristic alerts.
- Synthetic benchmark: 2,400 packets, 5 runs, median **100.99 packets/second**. Treat this only as a local synthetic CLI timing.
- No real labeled dataset or trained project model is present. Real-world detection quality, classifier metrics, and field throughput are unknown.
- Live capture was not tested because host packet-capture support is unavailable. Use authorized offline captures unless it is configured.
- No TLS/public-deployment security review; rate limiting is process-local and access-token revocation lists are not implemented.
- Host Python launcher is unavailable on this machine; prior backend checks ran in Docker.

## Important locations

- `nids_engine/`: replay, flow, features, rules, model loader, monitor.
- `ml/`: dataset preparation, provenance checks, training and evaluation.
- `backend/`, `database/`: FastAPI, authentication, persistence, migrations, audit, and WebSockets.
- `frontend/`: React dashboard pages and components.
- `compose.yaml`: local services and host dashboard port.
- `docs/PROJECT_REPORT.md`: plain-language status, architecture, test evidence, and next evidence required.
- `docs/HANDOFF.md`: detailed engineering handoff and demo instructions.
- `docs/DEPLOYMENT.md`: local start-up and authorized replay commands.
- `docs/KNOWN_LIMITATIONS.md`: explicit evidence, operations, and security limitations.

## Safe next actions

1. Keep the running stack available at `http://localhost:8080` while the user reviews it.
2. To populate the dashboard for a demonstration, offer or run the clearly labeled synthetic replay path in `docs/DEPLOYMENT.md`. It writes demo records into whichever database the monitor is configured to use; distinguish those records from real captures.
3. For real observations, use only a capture the user is authorized to analyze. Captures can contain sensitive metadata even though payloads are not emitted.
4. Do not claim AI/model detection or research accuracy until a matching trusted model and valid held-out evaluation report exist.
5. Keep generated captures, `.env`, datasets, and model artifacts out of Git.
6. Preserve the PostgreSQL volume. `docker compose down` keeps it; `docker compose down --volumes` deletes it.

## Project documents

- [Project report](docs/PROJECT_REPORT.md)
- [Final handoff](docs/HANDOFF.md)
- [Progress by implementation step](docs/PROGRESS.md)
- [Deployment](docs/DEPLOYMENT.md)
