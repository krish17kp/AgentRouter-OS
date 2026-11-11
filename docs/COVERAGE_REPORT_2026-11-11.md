# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,743 passed, 6 skipped |
| Line coverage | 91.15% (6,531 / 7,165 statements) |
| Branch coverage | 85.61% (1,803 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.89% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the local release-candidate worktree,
including the Rust feedback-learning and evaluation crates. The regression
includes Rust report-file, CLI platform scorer, and performance summary parity;
canonical LF report artifacts; Rust Markdown, grading, safety, provider,
feedback, and routing evaluator differential cases; plus explicit UTF-8
subprocess decoding alongside learning, quota-routing, doctor,
evaluation-metrics/provenance, sampler, schema, and registry compatibility
cases. The candidate package version is `0.5.0rc1`. The six skips are
environment-dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
