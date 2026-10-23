# Viva guide

Use this guide to explain what the repository actually implements. Distinguish software checks from evidence about detection quality. No real labeled dataset, trained model, or real-traffic performance result is included; the final software timing uses a synthetic fixture only.

## System and packet handling

### What does the system do?

It reads authorized PCAP/PCAPNG files, extracts packet metadata, groups packets into bidirectional flows, calculates a versioned feature vector, applies available heuristic rules and an optional trusted classifier, persists observations, and presents them through authenticated REST, WebSocket, and dashboard interfaces.

### Why replay PCAPs instead of capturing live traffic?

Offline replay is repeatable and does not require access to a live interface or a packet-capture driver. Live capture is optional and requires an explicitly chosen authorized interface plus host support; it has not been verified on this host.

### Does it store or display packet payloads?

No. The packet parser retains metadata needed for flow aggregation. The replay output omits payload bytes. Captures can still contain sensitive data, so use authorized files and keep them outside Git.

### How does bidirectional flow grouping work?

The flow builder creates a canonical endpoint pair from protocol, IP address, and port. Packets in either direction update the same flow while counters retain A-to-B and B-to-A orientation. Unkeyable packets are not given invented endpoint values.

### How are flows closed?

The builder supports idle and active timeouts, a maximum active-flow limit, and a final flush at end of replay. Event timestamps are handled with a monotonic watermark so out-of-order packet times do not move expiration backwards.

## Features, labels, and models

### How does training avoid data leakage?

The pipeline rejects extra identifier columns and invalid feature values, removes exact duplicates, rejects identical features with conflicting labels, and splits by capture group. No capture group is allowed across train, validation, and test splits. Model choice uses validation macro-F1; the held-out test split is evaluated once.

### Why is the feature schema versioned?

The version and explicit feature order let training and inference verify they use the same inputs. The loader checks schema, estimator structure, software versions, and an artifact checksum before deserialization.

### What models are implemented?

The training pipeline compares class-weighted Logistic Regression and Random Forest models. The inference interface can load a compatible artifact. The repository has no real trained model because no labeled project-schema dataset was supplied.

### What do the current results say about accuracy?

Nothing about real-world accuracy. Synthetic fixtures verify code paths only, and their metrics are not research results. A defensible evaluation requires provenance-tracked labels, independent capture groups, and a held-out test report.

### What kinds of detections are present?

The system supports model-class alerts and review rules including TCP SYN burst and high per-flow packet rate. Rule alerts are explainable signals for investigation, not proof that a host is compromised. No live attack or real-world alert-quality claim is made.

## Persistence, API, and access control

### Why persist both flows and alerts?

Persisting observations allows the API and dashboard to query the same records after offline replay. A flow, its prediction state, and its alerts are stored in one transaction to avoid reporting partial observations.

### Which database is implemented and which was tested?

SQLAlchemy models and Alembic migrations support PostgreSQL. SQLite-backed API tests pass. Isolated PostgreSQL integration tests cover authentication/session rotation, persisted alerts and WebSockets, capture history, analytics, user activation, refresh-session revocation, and last-active-admin safeguards. The local Compose PostgreSQL service also passed its health, migration, and API-readiness checks. See `HANDOFF.md` for exact evidence.

### How is the first administrator created?

There is no public registration endpoint. The local admin-provisioning command prompts for the password using hidden input. Administrators can create accounts in the User management dashboard or protected API and activate/deactivate accounts. Server-side role checks, audit records, session revocation, self-deactivation rejection, and PostgreSQL last-admin protection apply.

### How are sessions handled?

Access and refresh tokens are signed JWTs. Access tokens are short-lived. Refresh tokens rotate and their identifiers are stored as hashes; reuse of a rotated refresh token revokes the user's active refresh sessions. The dashboard holds tokens in memory, so a full page reload requires signing in again.

Failed logins are limited per direct socket peer and normalized username using a bounded, process-local fixed window. Blocked requests return `429` with `Retry-After`. Forwarded address headers are ignored. Multi-instance deployments need shared or edge rate limiting.

### How does alert streaming work?

The WebSocket sends a token in its first frame rather than in the URL. Clients can resume from a timestamp and alert ID. The server reads persisted alerts, including alerts written by a separate monitor process. Authenticated WebSocket delivery is covered by backend tests.

## Limitations to state clearly

- No real dataset, trained model, research metrics, or real classifier detections are included.
- A synthetic offline replay benchmark measures software behavior only; it is not network capacity, model quality, or detection effectiveness.
- The local PostgreSQL and Docker Compose deployment are verified, but have not had a security review for public exposure; Compose publishes only the dashboard on loopback and does not configure TLS.
- Live capture, distributed rate limiting, deployed TLS, and access-token revocation lists remain unimplemented or unverified.
- A checksum detects artifact changes against its metadata but does not authenticate the artifact's author. Only load models from a trusted source.
- Heuristic alerts can be noisy; thresholds require evaluation on authorized representative traffic.

The evidence and host-specific blockers are tracked in [PROGRESS.md](PROGRESS.md), [TESTING.md](TESTING.md), and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
