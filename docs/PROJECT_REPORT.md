# Project Report

- **Project:** AI-Based Real-Time Network Intrusion Detection and Traffic Monitoring System
- **Status date:** 26 October 2026
- **Implementation:** Complete through Step 20

## Executive summary

The project is a local network-traffic analysis application. It can read an authorized PCAP/PCAPNG capture, group packets into network flows, calculate versioned features, apply explainable detection rules, optionally run a verified machine-learning model, save results to PostgreSQL, and present persisted results in an authenticated dashboard.

The 20 planned implementation steps are complete and pushed to the GitHub `main` branch. The local Docker Compose application has now been started. PostgreSQL, the API, and the dashboard reported healthy at startup. The browser is currently on the Alerts page at <http://localhost:8080/alerts>.

This is a complete software pipeline, but it has not been evaluated on a supplied real dataset. No trained project model is included. Synthetic test results confirm software behavior only; they do not demonstrate real-world detection quality or classifier accuracy.

## What the application does

1. Reads packet metadata from an authorized offline PCAP or PCAPNG capture. Payloads are not emitted in replay output.
2. Groups packets into bidirectional flows and calculates stable, versioned features.
3. Applies explainable rules, including TCP SYN-burst and high packet-rate checks.
4. Optionally loads a trusted model only when its metadata, checksum, feature schema, and runtime compatibility checks pass.
5. Saves capture runs, flows, predictions, alerts, and audit events to PostgreSQL.
6. Serves authenticated APIs and an authenticated dashboard with role-based access.
7. Shows persisted alerts, flows, capture history, overview analytics, model/evaluation status, and administrator account management.
8. Streams persisted alerts to authenticated clients over WebSockets.

The dashboard does not capture network traffic by itself. Leaving the Alerts page open does not start monitoring; results appear after a capture is replayed through the monitor, or after an explicitly authorized live capture is configured and started.

## Current local runtime

| Item | Current state |
|---|---|
| Compose project | `nids-local` |
| PostgreSQL | Healthy at startup |
| API | Healthy at startup; migrations are applied during startup |
| Dashboard | Healthy at startup; served on loopback port `8080` |
| Browser page | `/alerts` |
| Local administrator | `admin` account provisioned after confirming no administrator existed |
| Account password | Shared in this conversation; intentionally omitted from repository files |
| Local database volume | Preserved; no volume-deleting command was run |
| New capture replayed during this startup | None |

The Step 20 synthetic smoke replay used an isolated disposable database. Its generated PCAP and disposable database were removed after the check, so that test did not seed the persistent `nids-local` database. Any older data already in the `nids-local` volume was left in place.

## Main parts

| Part | Responsibility |
|---|---|
| `nids_engine/` | Packet replay, flow construction, feature extraction, rules, optional model inference, and monitor CLI |
| `ml/` | Feature export, dataset provenance/validation, training, and held-out evaluation |
| `backend/` and `database/` | Authentication, API, database models, migrations, persistence, audit, and WebSockets |
| `frontend/` | React dashboard, login, overview, alerts, flows, capture history, model status, and admin user management |
| `scripts/` | Deterministic synthetic demo-capture generator and isolated replay benchmark |
| `compose.yaml` and `Dockerfile` files | Local PostgreSQL, API, monitor, and dashboard services |
| `docs/` | API, schema, deployment, test evidence, limitations, handoff, and academic guidance |

The dashboard routes are `/overview`, `/history`, `/alerts`, `/flows`, `/model`, and `/users`. The Users page is restricted to administrators.

## Verification and results

The final Step 20 verification recorded:

- Backend suite: **74 passed, 2 skipped**. The skipped tests are opt-in PostgreSQL integrations; PostgreSQL integration coverage was run separately during Step 18 and **2 passed**.
- Frontend suite: **15 passed** across 3 files.
- TypeScript and production dashboard build: passed. Initial JavaScript bundle: **267.48 kB** (84.75 kB gzip); chart bundle: **337.60 kB** (98.80 kB gzip).
- API, monitor, and dashboard container images: built successfully.
- Disposable synthetic demo: **192 packets, 8 flows, 8 heuristic alerts** persisted in its isolated database.
- Isolated synthetic replay benchmark: five runs of 2,400 packets each; median end-to-end CLI time **23.765572 seconds**, median **100.99 packets/second**. This includes startup and output work.

The benchmark is a machine-specific software timing on generated packets. It is not live capture capacity, tail latency, model performance, or proof that real attacks are detected.

## Evidence still needed

- A legally usable, provenance-tracked labeled dataset whose features match this project's schema.
- Independent capture groups for a valid held-out evaluation and real research metrics.
- A trained and verified model artifact before classifier results can be shown.
- Supported packet-capture drivers and an explicitly authorized interface before live capture can be evaluated.
- Security review and TLS before any public deployment. Login throttling is process-local; distributed rate limiting and access-token revocation lists are not implemented.

Until the evidence above exists, describe this as a completed detection software pipeline with explainable rules and optional model support. Do not report synthetic results as detection accuracy.

## GitHub status

The project is on branch `main`, synced with the user-provided GitHub repository at final Step 20 commit `388ae15` (`feat(demo): add reproducible benchmark and final handoff`). Steps 18 and 19 were separately pushed as `d67a705` and `13d1326`.

## Operating notes

- The local dashboard URL is <http://localhost:8080>.
- Use the generated local admin credential from this conversation. Do not copy it into Git, a report, or public documentation.
- For an authorized capture, follow [DEPLOYMENT.md](DEPLOYMENT.md). Place the file in the ignored local capture directory and run the one-shot Compose monitor service.
- For synthetic demonstration details and benchmark caveats, see [HANDOFF.md](HANDOFF.md) and [TESTING.md](TESTING.md).
- `docker compose down` stops the services while preserving the database volume. Do not use `docker compose down --volumes` unless you intend to erase the local database.

## Related documents

- [Project context for future work](../PROJECT_CONTEXT.md)
- [Final engineering handoff](HANDOFF.md)
- [Implementation progress](PROGRESS.md)
- [Deployment instructions](DEPLOYMENT.md)
- [Known limitations](KNOWN_LIMITATIONS.md)
