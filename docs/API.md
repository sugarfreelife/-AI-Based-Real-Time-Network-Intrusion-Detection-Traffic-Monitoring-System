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
| `POST /api/v1/auth/token` | Verify a username/password and return a 15-minute access token plus a 14-day refresh token. |
| `POST /api/v1/auth/refresh` | Rotate a refresh token and return a new token pair. |
| `POST /api/v1/auth/logout` | Revoke the supplied refresh token; returns 204. |
| `GET /api/v1/auth/me` | Return the authenticated user and current role. |
| `POST /api/v1/auth/users` | Create a user; administrator only. |
| `PATCH /api/v1/alerts/{id}/acknowledge` | Acknowledge an alert; analyst or administrator only. |
| `WS /api/v1/ws/alerts` | Stream newly persisted alerts to authenticated clients. |

All list responses use `{ "items": [], "total": 0, "limit": 50, "offset": 0 }`. Date filters require timezone-aware ISO-8601 values. `since` must not be later than `until`. Ordering is newest event time first with a stable ID tie-breaker.

Example requests:

```text
GET http://127.0.0.1:8000/api/v1/flows?protocol=TCP&limit=25&offset=0
GET http://127.0.0.1:8000/api/v1/alerts?severity=high&status=new&limit=25
```

Unknown records return 404. Invalid pagination, protocol, severity, status, or time ranges return 422. Database readiness returns 503 when the database cannot execute a simple query. Responses contain persisted observations only; the API does not create demo records or metrics.

## Authentication and roles

Run `python -m backend.app.auth_admin --username admin` after applying migrations to create the first admin. It prompts twice for the password without echoing it. There is no public registration route. Admins can create `admin`, `analyst`, or `viewer` accounts with:

```json
{"username":"analyst.one","password":"a-long-unique-passphrase","role":"analyst"}
```

Passwords are hashed with Argon2id through `pwdlib`. Usernames are normalized to lowercase and are unique. Passwords must be 12–128 characters. The role matrix is:

| Role | Read flows and alerts | Receive alert stream | Acknowledge alerts | Create users |
|---|---:|---:|---:|---:|
| viewer | Yes | Yes | No | No |
| analyst | Yes | Yes | Yes | No |
| admin | Yes | Yes | Yes | Yes |

Send the access token on REST requests as `Authorization: Bearer <access_token>`. Login accepts JSON such as `{"username":"admin","password":"..."}`. The response contains `access_token`, `refresh_token`, `token_type`, and `expires_in`. Keep the refresh token in a protected client store, rotate it through `/auth/refresh`, and discard the old value after a successful rotation. Reuse of a rotated token revokes all active refresh sessions for that account. Logout revokes the supplied refresh session; an already issued access token remains valid for up to 15 minutes.

`JWT_SECRET_KEY` is mandatory for login and must contain at least 32 UTF-8 bytes. Access and refresh JWTs use HS256 with explicit issuer, audience, required claims, and token-type checks. User role and active status are loaded from the database on each REST request, so permission changes take effect without waiting for token expiry. Health endpoints remain public. All other REST data routes require a bearer token.

Successful and failed login, refresh, logout, bootstrap/user creation, role denials, refresh-token reuse, and alert acknowledgement are recorded in `audit_events`. Passwords, access tokens, refresh tokens, and password hashes are not stored in audit details.

## Alert WebSocket

The server does not accept tokens in the URL. Connect to `/api/v1/ws/alerts`, then send the first frame within five seconds:

```json
{"access_token":"<access_token>"}
```

After validation, the server sends `{"type":"ready","user_id":"..."}`. New persisted alerts are sent as `{"type":"alert","data":{...alert fields...}}`. The connection polls persisted alerts, so alerts created by a separate monitor process are delivered too. On reconnect, clients may send `after_created_at` and `after_id` in the first frame to resume after their last received alert; omit both to receive alerts created after connection starts. The stream closes when the access token expires. Invalid/missing authentication closes with code 4401; database failures close with code 1011. The REST list endpoint remains the history source.

Use TLS when exposing the service beyond loopback. The current API does not implement login rate limiting or access-token revocation lists; keep access lifetimes short and restrict the service network until deployment hardening is added.
