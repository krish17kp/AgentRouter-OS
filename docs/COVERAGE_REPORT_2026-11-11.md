# Python coverage report — 2026-11-11

## Reproduction

```console
.venv/bin/python -m pytest --cov=agentrouter --cov-branch --cov-report=json:coverage.json -q
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,408 passed, 3 skipped |
| Line coverage including branch-aware run | 87.56% (6,295 / 7,059 statements) |
| Branch coverage | 82.08% (1,704 / 2,076 branches) |
| Required total coverage gate | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the current release candidate. The
three skipped tests are environment-dependent; CI remains responsible for
Windows and macOS confirmation. Coverage is not a replacement for mutation,
security, parity, or release evaluation gates.
