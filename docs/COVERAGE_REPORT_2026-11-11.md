# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,729 passed, 6 skipped |
| Line coverage | 91.01% (6,516 / 7,160 statements) |
| Branch coverage | 85.23% (1,795 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.69% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against RC commit `a4d2f79` plus the local
Rust feedback-learning and evaluation-metrics crates; the regression includes
nine learning, ten quota-routing, nine doctor, two evaluation-metrics and
provenance, six sampler, and one schema Python/Rust compatibility cases. The
candidate package version is
`0.5.0rc1`. The six skips are environment-
dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
