# Local container deployment and PCAP demo

This Compose stack is for a local academic demonstration. It defines PostgreSQL, the authenticated API, and the dashboard. The database and API are reachable only on the Compose network; the dashboard is published on the host loopback address. It does not configure TLS or make the system ready for public deployment. The pinned images have been built and the services verified on the development host; see [HANDOFF.md](HANDOFF.md) for the dated runtime evidence.

## Requirements

- Docker Desktop (or another Docker Engine) with Docker Compose v2.
- A locally generated PostgreSQL password and JWT signing key.
- An authorized PCAP/PCAPNG file only when replaying real observations. A clearly labelled synthetic fixture is available for a no-capture smoke demo.

The images use version-specific Python, Node, Nginx, and PostgreSQL tags; Python and frontend dependencies come from the checked-in lock files. Review and update these pins as part of planned maintenance.

## Start the services

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
```

Generate two local secrets and put them in `.env` as `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The database password should be hexadecimal because Compose inserts it into a PostgreSQL URL. Keep `.env` local; it is excluded from Git. Then validate and start the stack:

```powershell
docker compose config --quiet
docker compose up --build --detach
docker compose ps
```

The API waits for PostgreSQL, applies Alembic migrations, and then starts. The dashboard waits for the API readiness check. Open <http://127.0.0.1:8080>. Create the first administrator with hidden password entry:

```powershell
docker compose exec api python -m backend.app.auth_admin --username admin
```

Sign in with the account you created. With no imported capture, the dashboard should show its empty state. The project does not load sample alerts or fabricate metrics.

Login protection allows five failed attempts per direct socket peer and normalized username in a five-minute window, then returns `429` for five minutes. Override these defaults with `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `LOGIN_RATE_LIMIT_BLOCK_SECONDS`, and `LOGIN_RATE_LIMIT_MAX_ENTRIES` in `.env`. The API ignores forwarded client-address headers and the supported launcher disables Uvicorn proxy-header rewriting. Behind a proxy, requests share the proxy's peer address for each username; retain or add edge rate limiting for higher-traffic deployments.

## Replay an authorized PCAP into the dashboard

### Synthetic software demonstration

Generate a deterministic fixture using reserved documentation IP ranges, then replay it into the local dashboard:

```powershell
python -m scripts.synthetic_demo --force
docker compose --profile demo run --rm -e PCAP_PATH=/captures/synthetic-demo-not-real-network.pcap monitor
```

The generated file contains only synthetic TCP SYN packets and its name is shown in capture history. The rule alerts demonstrate software behavior; they are not real network traffic, an attack sample, or model evaluation. Generated PCAP files are ignored by Git. Re-running creates a new capture record unless `CAPTURE_ID` is explicitly set.

To measure the offline monitor on a temporary synthetic workload without a database or model:

```powershell
python -m scripts.benchmark_replay --flows 100 --syn-per-flow 24 --runs 5
```

The report includes end-to-end CLI wall time, packets per second, and derived milliseconds per input packet. It is machine-specific software timing on synthetic input, not field throughput, capture performance, detection quality, or research evidence.

### Authorized PCAP replay

Copy an authorized capture to the ignored local path `pcaps/demo.pcap`:

```powershell
Copy-Item "C:\path\to\authorized-capture.pcap" .\pcaps\demo.pcap
```

Run the one-shot monitor service:

```powershell
docker compose --profile demo run --rm monitor
```

The service mounts captures read-only, replays packet metadata through flow construction and the configured rules, and stores completed flow/prediction/alert records in PostgreSQL. Packet payloads are not emitted. Refresh the dashboard to review persisted records. If `ml/models/` contains a trusted project model and its matching metadata sidecar, set `MODEL_PATH=/models/<model-file>.joblib` in `.env`; Compose mounts that directory read-only into both the API and monitor. The Model & evaluation screen validates the configured artifact when first opened and displays a held-out report only when its checksum and model identity match. Restart the API after changing model files or `MODEL_PATH`. No model is included by default. For a safe retry after an interrupted replay, set `CAPTURE_ID` to the same UUID used on the first attempt. Leave it empty for a new capture run. Reuse the ID only for the same capture and model configuration; conflicting flow data is reported as an error.

## Service and data behavior

| Service | Purpose | Host exposure |
|---|---|---|
| `postgres` | PostgreSQL 17 database with health check and persistent named volume | None |
| `api` | Runs migrations, REST API, and authenticated alert WebSocket | None; internal Compose network |
| `dashboard` | Serves the built React app and proxies REST, health, and WebSocket traffic to the API | `127.0.0.1:8080` by default; change with `DASHBOARD_PORT` |
| `monitor` | Optional one-shot offline replay, enabled by the `demo` profile | None |

`docker compose down` stops and removes containers while keeping the named database volume. Deleting that volume removes the local database contents.

## Troubleshooting

- `Set POSTGRES_PASSWORD in .env` or `Set JWT_SECRET_KEY in .env`: fill both values in `.env`, then retry `docker compose config --quiet`.
- Dashboard reports the API unavailable: inspect `docker compose ps` and `docker compose logs api postgres`; the API readiness check requires a successful database query.
- The monitor reports a missing capture: check that `pcaps/demo.pcap` exists, or set `PCAP_PATH` to another path inside `/captures`.
- `docker compose` cannot reach the engine: start Docker Desktop and confirm its engine is available. Config parsing alone does not prove that images build or services run.

See [API.md](API.md), [DATABASE.md](DATABASE.md), [DETECTION.md](DETECTION.md), and [ML_METHODOLOGY.md](ML_METHODOLOGY.md) for API, persistence, detection, and model details.
