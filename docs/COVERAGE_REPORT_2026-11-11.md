# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,731 passed, 6 skipped |
| Line coverage | 91.06% (6,520 / 7,160 statements) |
| Branch coverage | 85.33% (1,797 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.76% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the local release-candidate worktree,
including the Rust feedback-learning and evaluation crates. The regression
includes the Rust Markdown report differential case alongside existing
learning, quota-routing, doctor, evaluation-metrics/provenance, sampler,
schema, and registry compatibility cases. The candidate package version is
`0.5.0rc1`. The six skips are environment-dependent; CI is responsible for
Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
