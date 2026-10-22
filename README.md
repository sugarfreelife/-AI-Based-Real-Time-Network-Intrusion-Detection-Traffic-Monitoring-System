# AI-Based Network Intrusion Detection and Traffic Monitoring

An academic project for processing authorized network traffic or offline PCAP files, grouping packets into flows, and presenting evidence-based network detections.

## Current status

This repository is at Step 9 of a 10-step implementation plan. It can parse PCAP/PCAPNG metadata, build bidirectional flows, extract versioned features, prepare labeled data, train compatible models, replay through optional inference, emit explainable alerts, persist observations, serve authenticated REST reads, acknowledge alerts by role, stream persisted alerts over authenticated WebSockets, and present persisted records in an authenticated dashboard. A local Docker Compose stack, offline replay workflow, and academic report/viva guides are documented. No real dataset or trained model is included, so no research metrics or real classifier detections are claimed. PostgreSQL and container runtime integration could not be exercised on this host; SQLite migration/API and Compose configuration checks pass.

## Planned technology

- Python with Scapy for packet parsing and replay
- Pandas, NumPy, and scikit-learn for reproducible feature processing and model evaluation
- FastAPI, SQLAlchemy, Alembic, and PostgreSQL for the service and persistence layer
- React, TypeScript, Vite, Tailwind CSS, and Recharts for the dashboard
- Docker Compose for supported local services

## Development plan

The work is split into at most 10 reviewable steps. Each completed step is intended to be committed and pushed before the next step begins. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

## Safety and data handling

Use only networks and captures you own or are authorized to analyze. PCAPs, datasets, model artifacts, and local environment files are excluded from Git by default. The project will distinguish fixture/demo data from real capture results and will not claim model metrics until a legitimate evaluation has run.

## Setup

Install the pinned project dependencies with `python -m pip install -r requirements-dev.lock`. Replay an authorized capture with:

```powershell
python -m nids_engine.replay --pcap .\path\to\authorized-capture.pcap
```

The command emits one JSON metadata record per packet and a capture summary. Packet payloads are not emitted or stored. Live capture requires an explicitly selected, authorized interface and host packet-capture support:

```powershell
python -m nids_engine.replay --live "INTERFACE NAME" --protocol TCP
```

Replay an authorized PCAP through flow processing and heuristic alerts (works without a trained model):

```powershell
python -m nids_engine.monitor `
  --pcap .\path\to\authorized-capture.pcap `
  --syn-burst-threshold 20
```

Add `--model .\ml\models\nids-model.joblib` to enable classifier output. The model must have its matching metadata sidecar and must be a trusted artifact produced by this project's training pipeline. Output flow records and alerts are JSON lines on standard output; the capture summary is written to standard error. Rule alerts remain available when model loading is missing or incompatible. See [docs/DETECTION.md](docs/DETECTION.md) for rule definitions and limitations.

Run the API with JWT authentication after configuring and migrating the database:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///./nids.db"
$env:JWT_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
python -m alembic upgrade head
python -m backend.app.auth_admin --username admin
python -m backend.app.cli --host 127.0.0.1 --port 8000
```

The administrator password is entered with hidden input. Admins can create analyst and viewer accounts through `POST /api/v1/auth/users`. Run the dashboard and API in separate terminals after starting the API and applying migrations:

```powershell
cd frontend
npm ci
npm run dev
```

The Vite development server proxies API and WebSocket requests to `http://127.0.0.1:8000`. For a separately hosted frontend, set `VITE_API_BASE_URL` at build time and configure the API's `CORS_ORIGINS` as a comma-separated allowlist for that frontend origin. Run the Python suite with `python -m pytest` and the dashboard checks with `npm test`, `npm run typecheck`, and `npm run build`. Environment findings and current constraints are tracked in [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Copy `.env.example` to `.env` for reference and supply real local values through your environment; never commit `.env`.

The ordered inference inputs and missing-value rules are documented in [docs/FEATURE_SCHEMA.md](docs/FEATURE_SCHEMA.md).

For labeled capture preparation and training commands, see [ml/data/README.md](ml/data/README.md) and [docs/ML_METHODOLOGY.md](docs/ML_METHODOLOGY.md). Dataset and generated model files are excluded from Git.

For database migrations, authentication, API filters, role permissions, and the WebSocket protocol, see [docs/DATABASE.md](docs/DATABASE.md) and [docs/API.md](docs/API.md).

For the local PostgreSQL/API/dashboard stack and authorized PCAP demo, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Academic handoff material is in [docs/VIVA_GUIDE.md](docs/VIVA_GUIDE.md) and [docs/REPORT_OUTLINE.md](docs/REPORT_OUTLINE.md).
