# Implementation Plan

Steps 1–10 established the initial implementation. On 2026-10-23, the user requested a ten-step extension, so the project now has a 20-step maximum. Each step leaves a coherent, reviewable state. After implementing and verifying a step, update `docs/PROGRESS.md`, create one Git commit for that step, and push it to the configured GitHub remote before starting the next step. Do not mark unavailable infrastructure or data as successful.

| Step | Scope | Completion evidence |
|---|---|---|
| 1. Audit and foundation | Inspect the empty workspace and tools; initialize Git; add safety-oriented ignore rules, environment template, README, architecture outline, progress and limitation records, and this plan. | Audit facts recorded; clean first commit; remote push status recorded. |
| 2. Packet ingestion | Add packet metadata types, Scapy parsing, offline PCAP/PCAPNG replay, capture statistics, CLI, and controlled packet tests. Keep live capture optional and authorized. | PASS: parser and replay tests pass; CLI help works; live-capture constraints documented. |
| 3. Flows and features | Add deterministic bidirectional flow construction, expiration, a versioned feature schema, validation, and unit tests. | PASS: reverse packets share a flow; timeout, bounds, feature ordering, ranges, and calculations are tested. |
| 4. Dataset and training | Add provenance-aware dataset preparation, leakage checks, reproducible splits, baseline and Random Forest training, evaluation, and artifact metadata. | PASS: 36 tests verify parsing through fixture training, CLI help, and output protections. BLOCKED: no real labeled dataset is present, so no research metrics/model are reported. |
| 5. Inference and alerts | Load trusted model artifacts, validate schema compatibility and checksum, connect replay to inference, and create explainable/deduplicated alerts. | PASS: model load/prediction, missing/incompatible/corrupt states, PCAP-to-model-to-alert integration, heuristic rules, and deduplication tests pass. BLOCKED: no real model is available without labeled data. |
| 6. Persistence and REST API | Add PostgreSQL schema/migrations, data services, FastAPI endpoints, validation, pagination, and health reporting. | PASS: 48 tests, SQLite migration/schema-drift check, API filters/pagination/readiness, and monitor persistence integration. BLOCKED: PostgreSQL server integration unavailable on this host. |
| 7. WebSockets and access control | Add authenticated alert streaming, JWT lifecycle, Argon2id, role permissions, audit events, and authorization tests. | Auth, permissions, WebSocket delivery, and recovery behavior are verified. |
| 8. Dashboard | Add a strict TypeScript React dashboard backed by real APIs, with honest empty/loading/error states, useful filters, and alert actions. | Type checks, frontend tests, and production build pass; no fabricated production metrics. |
| 9. Reproducible operation and docs | Add supported Docker Compose services, PCAP demo workflow, API/database/ML docs, viva guide, and report structure based on actual implementation. | Compose configuration validates; documented commands match available behavior. |
| 10. Integration and handoff | Run the available end-to-end checks, inspect security and Git exclusions, measure only what can be measured, capture evidence, and complete the academic handoff. | Results are labeled PASS, FAIL, BLOCKED, or NOT TESTED with evidence and remaining limitations. |

## Requested extension: Steps 11–20

| Step | Scope | Completion evidence |
|---|---|---|
| 11. PostgreSQL integration coverage | Add opt-in integration coverage for real PostgreSQL migrations, authentication/session lifecycle, persisted alerts, authorization, and WebSocket delivery. Keep it isolated from the user's normal database. | PASS: tests run against a disposable PostgreSQL database and clean up their rows. |
| 12. Capture-run lifecycle | Persist one run record with source identity, timestamps, outcome, model state, packet/flow/alert counts, and failure details; update it as the monitor executes. | PASS: completed and failed run states are persisted transactionally without packet payloads. |
| 13. Retry-safe replay identity | Allow a stable operator-supplied capture ID and make per-flow persistence idempotent for replays with that ID. | PASS: a retry does not duplicate observations, predictions, or alerts; conflicting data for an ID is rejected. |
| 14. Capture history API | Add authenticated, paginated capture-run list/detail reads with time and status filters. | PASS: schemas, permissions, validation, and retry-aware counters reflect persisted runs. |
| 15. Overview analytics API | Add authenticated summary and time-bucket queries over persisted flows/alerts, with timezone-aware ranges and empty-database behavior. | PASS: counts derive from persisted rows, respect UTC ranges, and return zero-filled time buckets. |
| 16. Overview and history dashboard | Add a real-data overview and historical attack/traffic analysis screens with truthful empty/loading/error states and URL-backed ranges. | PASS: overview reads summary/timeline APIs; capture history reads the paginated run API; dates, bucket, status, page, and limit are URL-backed; empty/loading/error/retry states and frontend checks pass. |
| 17. Model status and evaluation view | Expose only configured trusted model metadata/metrics and add a dashboard view for model availability and actual evaluation reports. | PASS: unavailable/untrusted model state is explicit; metrics appear only when a valid report exists. |
| 18. Administrator user management | Add admin-only user listing and safe account activation changes, with audit records and a usable dashboard screen. | PASS: admin-only list/create/status controls, status audit records, refresh-session revocation, self/last-admin safeguards, SQLite and PostgreSQL integration coverage, and dashboard checks pass. |
| 19. Login abuse controls | Add bounded login throttling and configurable limits with safe client-address handling and clear 429 behavior. | PASS: configurable fixed-window limits, bounded overflow behavior, 429/Retry-After, success reset, lockout expiry, audit minimization, and spoofed-forwarding checks pass. |
| 20. Performance, reproducible demo, and final handoff | Report measured replay throughput/latency, add a clearly labelled local demonstration workflow, record deployment/integration evidence, and update the academic handoff. | PASS/NOT TESTED/BLOCKED evidence is explicit; no real-data metrics or live capture claims are fabricated. |

## Step boundaries

- A step may be narrowed if a verified environment or data blocker prevents safe completion. Record the blocker and finish independent work in that step.
- Do not expand beyond the requested 20-step maximum. Keep later maintenance outside this implementation plan.
- Do not download large datasets automatically, capture live traffic without authorization, commit secrets, or invent metrics.
- The user-provided GitHub remote is configured as `origin`; push each completed step before proceeding.
