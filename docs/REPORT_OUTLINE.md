# Academic report outline

This is a structure for a report about the implemented project. Replace prompts with measured evidence and citations. Do not turn software fixtures, planned features, or unavailable infrastructure into research findings.

## Front matter

- Title page, author, institution, supervisor, and submission date.
- Abstract (problem, implemented method, evidence actually available, and limitations).
- Keywords and table of contents.

## 1. Introduction

- Network intrusion detection problem and project scope.
- Research question and objectives.
- Scope boundaries: authorized offline traffic, metadata processing, and explainable review alerts.
- Contributions that are present in the repository.

## 2. Background and related work

- Signature/rule-based and machine-learning approaches to network IDS.
- Flow-level feature engineering and group-aware evaluation.
- The chosen dataset's source, collection process, license, and citation if a real dataset is later used.
- Compare prior work with the project only using sourced, comparable evidence.

## 3. Requirements and methodology

- Functional and non-functional requirements.
- Authorized PCAP replay and payload-handling choices.
- Flow definition, timeout policy, feature schema, and missing-value treatment.
- Dataset provenance, label source, duplicate checks, and capture-group split design.
- Candidate algorithms, training-only preprocessing, selection metric, and held-out evaluation plan.

## 4. System design and implementation

- Architecture and data-flow diagram based on `ARCHITECTURE.md`.
- Packet parser, flow builder, feature extractor, inference/rule interface, persistence, API, authentication, WebSocket, and dashboard.
- Model artifact validation and deployment workflow.
- Privacy, authorization, audit, and operational decisions.

## 5. Experimental setup

When a real dataset becomes available, document:

- Exact source/version, download date, license, hashes, capture groups, and label provenance.
- Hardware, OS, Python/package versions, configuration, and random seed.
- Exclusions, class balance, preprocessing, grouping, and split counts.
- Baseline and comparison settings; define metrics before inspecting the test set.

If no real dataset is available at submission time, state that empirical detection evaluation was blocked and omit unsupported metric tables.

## 6. Results

Report only measured held-out results. Include test-group counts and class support with accuracy, macro precision/recall/F1, per-class scores, and confusion matrix. Separate training/validation decisions from final test performance. If a result was not measured, label it **NOT TESTED**; if the infrastructure or data prevented it, label it **BLOCKED** and give the evidence.

| Evaluation item | Result | Evidence/source |
|---|---|---|
| Real labeled dataset and capture groups | BLOCKED until supplied | Dataset manifest and source records |
| Held-out classifier metrics | NOT AVAILABLE | Training report from a real verified dataset |
| Software behavior on controlled fixtures | PASS for covered tests | `TESTING.md`; software correctness only |
| PostgreSQL service integration | Local Compose service verified on 2026-10-22 | `HANDOFF.md` and `TESTING.md` runtime record |
| Container execution | PASS for image build, migrations, service health, and dashboard/health HTTP | `HANDOFF.md` and `TESTING.md`; PCAP replay still requires a supplied authorized capture |

## 7. Discussion

- Interpret results against the stated research question.
- False positives/negatives, threshold sensitivity, dataset bias, capture-group independence, and distribution shift.
- Why offline evaluation does not establish live-network effectiveness.
- Privacy and operational limits of metadata-only analysis.

## 8. Threats to validity and limitations

- Ground-truth quality and provenance.
- Flow/feature implementation mismatch with upstream datasets.
- Class imbalance, duplicate or near-duplicate flows, unseen attack families, and domain shift.
- Missing real dataset/model results, PostgreSQL integration, or deployment checks if still blocked.
- Security limitations such as unconfigured TLS and absent login rate limiting.

## 9. Conclusion and future work

- Answer the research question only to the extent supported by evidence.
- Separate completed software work from planned evaluation and deployment.
- Next steps: prepare provenance-tracked labels, evaluate on independent captures, verify PostgreSQL and Compose on a capable host, and complete the security review.

## References and appendices

- Cite dataset sources, papers, package/tool versions, and external technical claims in the required institutional style.
- Append the feature schema, dataset manifest, exact commands, environment record, evaluation report, test results, and limitations matrix where relevant.
- Do not include private captures, credentials, raw personal data, or fabricated example metrics.
