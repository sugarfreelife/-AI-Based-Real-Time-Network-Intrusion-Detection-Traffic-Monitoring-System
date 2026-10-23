# REST API

## Run locally

Install the pinned backend dependencies, configure `DATABASE_URL`, apply migrations, then start the API:

```powershell
python -m pip install -r requirements-backend.lock
$env:DATABASE_URL = "sqlite+pysqlite:///./nids.db"
python -m alembic upgrade head
python -m backend.app.cli --host 127.0.0.1 --port 8000
```

The API binds to loopback by default. Set `JWT_SECRET_KEY` to a generated value of at least 32 UTF-8 bytes before starting it. Never use a checked-in or shared development key. Interactive OpenAPI docs are at `http://127.0.0.1:8000/docs`.

Browser clients on a separate origin must be listed in `CORS_ORIGINS` as a comma-separated exact-origin allowlist, such as `http://localhost:5173`. Credentials are not enabled for CORS; the dashboard sends bearer tokens in the `Authorization` header and does not use cookies. The Vite development server proxies API and WebSocket traffic, so its default local workflow is same-origin.

For flow ingestion, run the PCAP monitor with the same URL:

```powershell
python -m nids_engine.monitor `
  --pcap .\path\to\authorized-capture.pcap `
  --database-url $env:DATABASE_URL
```

The monitor creates a new `capture_id` per run. Supply `--capture-id <uuid>` to reuse an ID after an interrupted replay. Identical flow observations are skipped and conflicting data for an existing ID is rejected. Each flow, prediction status, and related alerts are inserted atomically.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health/live` | Process liveness; does not require the database. |
| `GET /health/ready` | Execute a database connectivity check; returns 503 when unavailable. |
| `GET /api/v1/captures` | List capture runs with `limit` (1–100), `offset`, `status`, `since`, and `until` filters. |
| `GET /api/v1/captures/{capture_id}` | Read one capture run, including packet, flow, prediction, alert, retry, and failure counters. |
| `GET /api/v1/analytics/summary` | Count persisted flows, alerts, and capture runs in a UTC time range, with protocol/severity/status breakdowns. |
| `GET /api/v1/analytics/timeline` | Return UTC hourly or daily flow and alert counts, including zero-count buckets. |
| `GET /api/v1/model/status` | Return configured-model availability and a checksum-matched held-out evaluation report when valid. |
| `GET /api/v1/flows` | List flows with `limit` (1–100), `offset`, `protocol`, `since`, and `until` filters. |
| `GET /api/v1/flows/{id}` | Read one persisted flow with its prediction result. `{id}` is the database record ID. |
| `GET /api/v1/alerts` | List alerts with `limit`, `offset`, `severity`, `status`, `detection_code`, `since`, and `until` filters. |
| `GET /api/v1/alerts/{id}` | Read one alert. |
| `POST /api/v1/auth/token` | Verify a username/password and return a 15-minute access token plus a 14-day refresh token. |
| `POST /api/v1/auth/refresh` | Rotate a refresh token and return a new token pair. |
| `POST /api/v1/auth/logout` | Revoke the supplied refresh token; returns 204. |
| `GET /api/v1/auth/me` | Return the authenticated user and current role. |
| `GET /api/v1/auth/users` | Return a paginated, newest-first user register; administrator only. Accepts `limit` (1–100) and `offset` (0 or greater). |
| `POST /api/v1/auth/users` | Create a user; administrator only. |
| `PATCH /api/v1/auth/users/{user_id}/status` | Activate or deactivate an account; administrator only. Body: `{"is_active":false}`. |
| `PATCH /api/v1/alerts/{id}/acknowledge` | Acknowledge an alert; analyst or administrator only. |
| `WS /api/v1/ws/alerts` | Stream newly persisted alerts to authenticated clients. |

All list responses use `{ "items": [], "total": 0, "limit": 50, "offset": 0 }`. Date filters require timezone-aware ISO-8601 values. `since` must not be later than `until`. Capture history filters `started_at`; its status is `running`, `completed`, `partial`, or `failed`. Ordering is newest start time first with a stable capture ID tie-breaker. Analytics endpoints default to the latest 24 hours in UTC when no range is supplied. Summary flow counts use `ended_at`, alert counts use `occurred_at`, and capture counts use `started_at`. Timeline buckets may be `hour` (up to 31 days) or `day` (up to 366 days); omitted buckets default to hour. Empty buckets are returned as zeros. The model status endpoint is available to any signed-in role. `MODEL_PATH` must point to a trusted project model in the API container; status is inspected on first request and cached until the API restarts. A report is displayed only when it validates, matches the configured model version, describes held-out capture groups, and matches the SHA-256 recorded by the model metadata. The checksum detects changes relative to metadata but is not a signature or proof of dataset provenance.

Example requests:

```text
GET http://127.0.0.1:8000/api/v1/flows?protocol=TCP&limit=25&offset=0
GET http://127.0.0.1:8000/api/v1/alerts?severity=high&status=new&limit=25
GET http://127.0.0.1:8000/api/v1/captures?status=failed&limit=25
GET http://127.0.0.1:8000/api/v1/captures/550e8400-e29b-41d4-a716-446655440000
GET http://127.0.0.1:8000/api/v1/analytics/summary?since=2026-10-22T00:00:00Z&until=2026-10-23T00:00:00Z
GET http://127.0.0.1:8000/api/v1/analytics/timeline?bucket=hour&since=2026-10-22T00:00:00Z&until=2026-10-23T00:00:00Z
GET http://127.0.0.1:8000/api/v1/model/status
```

Unknown records return 404. Invalid pagination, protocol, severity, status, or time ranges return 422. Self-deactivation and attempts to deactivate the last active administrator return 409. Database readiness returns 503 when the database cannot execute a simple query. Responses contain persisted observations only; the API does not create demo records or metrics.

## Authentication and roles

Run `python -m backend.app.auth_admin --username admin` after applying migrations to create the first admin. It prompts twice for the password without echoing it. There is no public registration route. Admins can create `admin`, `analyst`, or `viewer` accounts with:

```json
{"username":"analyst.one","password":"a-long-unique-passphrase","role":"analyst"}
```

Passwords are hashed with Argon2id through `pwdlib`. Usernames are normalized to lowercase and are unique. Passwords must be 12–128 characters. The user register returns public account fields only and is paginated newest first. Status changes are audited without credentials; deactivation revokes all refresh sessions, and inactive users fail REST authentication immediately. An administrator cannot deactivate their own account, and PostgreSQL serializes administrator deactivation checks so the last active administrator cannot be removed, even by concurrent requests. The role matrix is:

| Role | Read capture, flow, alert, analytics, and model status | Receive alert stream | Acknowledge alerts | List users | Create users | Change account status |
|---|---:|---:|---:|---:|---:|---:|
| viewer | Yes | Yes | No | No | No | No |
| analyst | Yes | Yes | Yes | No | No | No |
| admin | Yes | Yes | Yes | Yes | Yes | Yes |

Send the access token on REST requests as `Authorization: Bearer <access_token>`. Login accepts JSON such as `{"username":"admin","password":"..."}`. The response contains `access_token`, `refresh_token`, `token_type`, and `expires_in`. Keep the refresh token in a protected client store, rotate it through `/auth/refresh`, and discard the old value after a successful rotation. Reuse of a rotated token revokes all active refresh sessions for that account. Logout revokes the supplied refresh session; an already issued access token remains valid for up to 15 minutes.

`JWT_SECRET_KEY` is mandatory for login and must contain at least 32 UTF-8 bytes. Access and refresh JWTs use HS256 with explicit issuer, audience, required claims, and token-type checks. User role and active status are loaded from the database on each REST request, so permission changes take effect without waiting for token expiry. Health endpoints remain public. All other REST data routes require a bearer token.

Login throttling uses `LOGIN_RATE_LIMIT_ATTEMPTS` (default 5 failures; allowed 1–100), `LOGIN_RATE_LIMIT_WINDOW_SECONDS` (default 300; allowed 1–86,400), `LOGIN_RATE_LIMIT_BLOCK_SECONDS` (default 300; allowed 1–86,400), and `LOGIN_RATE_LIMIT_MAX_ENTRIES` (default 10,000; allowed 2–100,000). Values are validated at startup. Failed attempts are counted by direct socket peer and normalized username in a thread-safe, bounded in-memory fixed-window limiter. Once blocked, login returns `429` with a `Retry-After` header. The first blocked request in a window is audited; repeated blocked requests do not add an audit row each time. A successful login clears that exact peer/username key. When the key store reaches capacity, new keys share an overflow bucket, which can temporarily throttle unrelated new keys during high username churn. The implementation ignores `X-Forwarded-For`; the supported API launcher also disables Uvicorn proxy-header rewriting. Behind a reverse proxy, the API sees the proxy's socket address, so clients using the same username share a bucket. Each API process has its own limiter; use a trusted edge limiter or shared store for multi-instance deployments.

Successful and failed login, rate-limited login (once per blocked key/window), refresh, logout, bootstrap/user creation, account status changes, role denials, refresh-token reuse, and alert acknowledgement are recorded in `audit_events`. Passwords, access tokens, refresh tokens, password hashes, and client addresses are not stored in audit details.

## Alert WebSocket

The server does not accept tokens in the URL. Connect to `/api/v1/ws/alerts`, then send the first frame within five seconds:

```json
{"access_token":"<access_token>"}
```

After validation, the server sends `{"type":"ready","user_id":"..."}`. New persisted alerts are sent as `{"type":"alert","data":{...alert fields...}}`. The connection polls persisted alerts, so alerts created by a separate monitor process are delivered too. On reconnect, clients may send `after_created_at` and `after_id` in the first frame to resume after their last received alert; omit both to receive alerts created after connection starts. The stream closes when the access token expires. Invalid/missing authentication closes with code 4401; database failures close with code 1011. The REST list endpoint remains the history source.

Use TLS when exposing the service beyond loopback. Access-token revocation lists and a distributed rate-limit store are not implemented; keep access lifetimes short and use an edge limiter for multi-instance deployments.
