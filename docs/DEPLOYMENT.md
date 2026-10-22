# Local container deployment and PCAP demo

This Compose stack is for a local academic demonstration. It defines PostgreSQL, the authenticated API, and the dashboard. The database and API are reachable only on the Compose network; the dashboard is published on the host loopback address. It does not configure TLS or make the system ready for public deployment. Compose configuration parses on the current host, but image builds and service startup remain unverified because this host cannot access its Docker engine.

## Requirements

- Docker Desktop (or another Docker Engine) with Docker Compose v2.
- A locally generated PostgreSQL password and JWT signing key.
- An authorized PCAP/PCAPNG file only when running the optional replay demo.

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

The API waits for PostgreSQL, applies Alembic migrations, and then starts. The dashboard waits for the API readiness check. Create the first administrator with hidden password entry:

```powershell
docker compose exec api python -m backend.app.auth_admin --username admin
```

Open <http://127.0.0.1:8080> and sign in. With no imported capture, the dashboard should show its empty state. The project does not load sample alerts or fabricate metrics.

## Replay an authorized PCAP into the dashboard

Copy an authorized capture to the ignored local path `pcaps/demo.pcap`:

```powershell
Copy-Item "C:\path\to\authorized-capture.pcap" .\pcaps\demo.pcap
```

Run the one-shot monitor service:

```powershell
docker compose --profile demo run --rm monitor
```

The service mounts captures read-only, replays packet metadata through flow construction and the configured rules, and stores completed flow/prediction/alert records in PostgreSQL. Packet payloads are not emitted. Refresh the dashboard to review persisted records. If `ml/models/` contains a trusted project model and its matching metadata sidecar, set `MODEL_PATH=/models/<model-file>.joblib` in `.env` before running the monitor. No model is included by default.

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
