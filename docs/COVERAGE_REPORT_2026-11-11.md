# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,711 passed, 6 skipped |
| Line coverage | 90.99% (6,515 / 7,160 statements) |
| Branch coverage | 85.19% (1,794 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.67% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against RC commit `a423ac5` plus the local
Rust doctor usage-check slice; the regression includes ten quota-routing
Python/Rust differential cases and nine doctor compatibility cases. The
candidate package version is
`0.5.0rc1`. The six skips are environment-
dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
