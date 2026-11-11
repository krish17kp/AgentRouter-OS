# Python coverage report — 2026-11-11

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
PYTHONPATH=. python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,696 passed, 6 skipped |
| Line coverage | 90.98% (6,514 / 7,160 statements) |
| Branch coverage | 85.14% (1,793 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.65% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against RC code at `b26528b` (Rust doctor
probe and the `0.5.0rc1` candidate package version). The subsequent parity
matrix commit changes documentation only. The six skips are environment-
dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
