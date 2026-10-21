# AI-Based Network Intrusion Detection and Traffic Monitoring

An academic project for processing authorized network traffic or offline PCAP files, grouping packets into flows, and presenting evidence-based network detections.

## Current status

This repository is at Step 1 of a 10-step implementation plan. The initial audit and project documentation are in place. Packet capture, flow processing, machine-learning inference, persistence, API, authentication, WebSockets, and dashboard features are not implemented yet.

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

The application is not runnable yet. Environment findings and current constraints are tracked in [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). For future local configuration, copy `.env.example` to `.env` and supply local values; never commit `.env`.
