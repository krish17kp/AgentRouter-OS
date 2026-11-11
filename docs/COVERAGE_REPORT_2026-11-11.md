# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,893 passed, 6 skipped |
| Line coverage | 92.16% (6,604 / 7,166 statements) |
| Branch coverage | 87.27% (1,838 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.05% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the local release-candidate worktree,
including the Rust feedback-learning and evaluation crates. The regression
includes CLINC150, Banking77, MASSIVE, LongBench v2, and SWE-bench raw-row normalization parity plus shared Rust fixture-adapter
parity for six external datasets plus full
AgentRouter gold-adapter parity for metadata, availability, description, all
165 records, checksum, and seeded sampling; annotation duplicate/leakage and
split safety differential checks; Rust report-file,
CLI platform scorer, performance summary, annotation schema/datetime parity,
graph-impact, full annotation-pack parity, annotation file/hash parity,
deterministic candidate-generation parity, rules/learned/hybrid annotation
comparison with exact seeded bootstrap confidence intervals, and Python/Rust
graph-signal malformed-shape, four-entry LRU cache, and contextual Unicode
lowercase parity;
canonical LF report artifacts; Python/Rust context-band report and split-leak
parity; package export and distribution-version contracts; Rust Markdown, grading, safety, provider,
feedback, and routing evaluator differential cases; plus explicit UTF-8
subprocess decoding alongside learning, quota-routing, doctor,
evaluation-metrics/provenance, sampler, schema, and registry compatibility
cases. The candidate package version is `0.5.0rc1`. The six skips are
environment-dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
