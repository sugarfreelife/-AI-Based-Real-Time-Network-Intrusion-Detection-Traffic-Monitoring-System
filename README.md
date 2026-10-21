# AI-Based Network Intrusion Detection and Traffic Monitoring

An academic project for processing authorized network traffic or offline PCAP files, grouping packets into flows, and presenting evidence-based network detections.

## Current status

This repository is at Step 3 of a 10-step implementation plan. It can parse packet metadata from PCAP/PCAPNG files, build deterministic bidirectional flows, and extract versioned numeric features. The CLI currently exposes packet replay; flow and feature APIs are available as Python modules. Machine-learning training/inference, persistence, API, authentication, WebSockets, and dashboard features are not implemented yet.

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

Run the packet ingestion tests with `python -m pytest`. Environment findings and current constraints are tracked in [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). For later services, copy `.env.example` to `.env` and supply local values; never commit `.env`.

The ordered inference inputs and missing-value rules are documented in [docs/FEATURE_SCHEMA.md](docs/FEATURE_SCHEMA.md).
