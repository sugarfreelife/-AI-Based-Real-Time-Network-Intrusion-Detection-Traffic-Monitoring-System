# Implementation Plan

The build is limited to 10 steps. Each step should leave a coherent, reviewable state. After implementing and verifying a step, update `docs/PROGRESS.md`, create one Git commit for that step, and push it to the configured GitHub remote before starting the next step. Do not mark unavailable infrastructure or data as successful.

| Step | Scope | Completion evidence |
|---|---|---|
| 1. Audit and foundation | Inspect the empty workspace and tools; initialize Git; add safety-oriented ignore rules, environment template, README, architecture outline, progress and limitation records, and this plan. | Audit facts recorded; clean first commit; remote push status recorded. |
| 2. Packet ingestion | Add packet metadata types, Scapy parsing, offline PCAP/PCAPNG replay, capture statistics, CLI, and controlled packet tests. Keep live capture optional and authorized. | PASS: parser and replay tests pass; CLI help works; live-capture constraints documented. |
| 3. Flows and features | Add deterministic bidirectional flow construction, expiration, a versioned feature schema, validation, and unit tests. | PASS: reverse packets share a flow; timeout, bounds, feature ordering, ranges, and calculations are tested. |
| 4. Dataset and training | Add provenance-aware dataset preparation, leakage checks, reproducible splits, baseline and Random Forest training, evaluation, and artifact metadata. | PASS: 36 tests verify parsing through fixture training, CLI help, and output protections. BLOCKED: no real labeled dataset is present, so no research metrics/model are reported. |
| 5. Inference and alerts | Load trusted model artifacts, validate schema compatibility and checksum, connect replay to inference, and create explainable/deduplicated alerts. | PASS: model load/prediction, missing/incompatible/corrupt states, PCAP-to-model-to-alert integration, heuristic rules, and deduplication tests pass. BLOCKED: no real model is available without labeled data. |
| 6. Persistence and REST API | Add PostgreSQL schema/migrations, data services, FastAPI endpoints, validation, pagination, and health reporting. | Migration/API checks pass where database infrastructure permits; blocked checks are explicit. |
| 7. WebSockets and access control | Add authenticated alert streaming, JWT lifecycle, Argon2id, role permissions, audit events, and authorization tests. | Auth, permissions, WebSocket delivery, and recovery behavior are verified. |
| 8. Dashboard | Add a strict TypeScript React dashboard backed by real APIs, with honest empty/loading/error states, useful filters, and alert actions. | Type checks, frontend tests, and production build pass; no fabricated production metrics. |
| 9. Reproducible operation and docs | Add supported Docker Compose services, PCAP demo workflow, API/database/ML docs, viva guide, and report structure based on actual implementation. | Compose configuration validates; documented commands match available behavior. |
| 10. Integration and handoff | Run the available end-to-end checks, inspect security and Git exclusions, measure only what can be measured, capture evidence, and complete the academic handoff. | Results are labeled PASS, FAIL, BLOCKED, or NOT TESTED with evidence and remaining limitations. |

## Step boundaries

- A step may be narrowed if a verified environment or data blocker prevents safe completion. Record the blocker and finish independent work in that step.
- Do not expand beyond 10 steps. Keep later work within the closest planned step.
- Do not download large datasets automatically, capture live traffic without authorization, commit secrets, or invent metrics.
- The user-provided GitHub remote is configured as `origin`; push each completed step before proceeding.
