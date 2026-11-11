# Python coverage report — 2026-11-11

## Reproduction

```console
.venv/bin/pytest -q --cov=agentrouter --cov-branch --cov-report=json:coverage.json --cov-report=term
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,658 passed, 6 skipped |
| Line coverage | 90.96% (6,513 / 7,160 statements) |
| Branch coverage | 85.09% (1,792 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 89.63% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the release candidate with dashboard, observability, and harness compatibility probes, plus offline refresh, diagnostics, registry-edge, and soak tests. The six skips are environment-dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation gates.
