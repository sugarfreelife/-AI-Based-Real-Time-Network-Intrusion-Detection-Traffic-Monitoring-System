# REST API

## Run locally

Install the pinned backend dependencies, configure `DATABASE_URL`, apply migrations, then start the API:

```powershell
python -m pip install -r requirements-backend.lock
$env:DATABASE_URL = "sqlite+pysqlite:///./nids.db"
python -m alembic upgrade head
python -m backend.app.cli --host 127.0.0.1 --port 8000
```

The API binds to loopback by default. It has no authentication in Step 6; keep it local until Step 7 adds access control. Interactive OpenAPI docs are at `http://127.0.0.1:8000/docs`.

For flow ingestion, run the PCAP monitor with the same URL:

```powershell
python -m nids_engine.monitor `
  --pcap .\path\to\authorized-capture.pcap `
  --database-url $env:DATABASE_URL
```

The monitor creates a new `capture_id` per run. Each flow, prediction status, and related alerts are inserted atomically.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health/live` | Process liveness; does not require the database. |
| `GET /health/ready` | Execute a database connectivity check; returns 503 when unavailable. |
| `GET /api/v1/flows` | List flows with `limit` (1–100), `offset`, `protocol`, `since`, and `until` filters. |
| `GET /api/v1/flows/{id}` | Read one persisted flow with its prediction result. `{id}` is the database record ID. |
| `GET /api/v1/alerts` | List alerts with `limit`, `offset`, `severity`, `status`, `detection_code`, `since`, and `until` filters. |
| `GET /api/v1/alerts/{id}` | Read one alert. |

All list responses use `{ "items": [], "total": 0, "limit": 50, "offset": 0 }`. Date filters require timezone-aware ISO-8601 values. `since` must not be later than `until`. Ordering is newest event time first with a stable ID tie-breaker.

Example requests:

```text
GET http://127.0.0.1:8000/api/v1/flows?protocol=TCP&limit=25&offset=0
GET http://127.0.0.1:8000/api/v1/alerts?severity=high&status=new&limit=25
```

Unknown records return 404. Invalid pagination, protocol, severity, status, or time ranges return 422. Database readiness returns 503 when the database cannot execute a simple query. Responses contain persisted observations only; the API does not create demo records or metrics.

## Current security boundary

Step 6 provides read-only REST endpoints and local monitor-to-database ingestion. It does not provide authentication, authorization, alert acknowledgement, or a public network deployment. The API runner binds to `127.0.0.1` unless an operator explicitly overrides `--host`. Authentication and role controls are planned for Step 7.
