# Python coverage report — 2026-11-14

## Reproduction

Run from the repository root:

```console
uv sync --extra dev --extra server --extra property --extra mcp
uv run pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 2,113 passed, 5 skipped |
| Line coverage | 92.54% (6,678 / 7,216 statements) |
| Branch coverage | 87.66% (1,862 / 2,124 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.43% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the release-candidate worktree. It
includes the simultaneous Python SQLite schema-migration regression, exact
idempotency byte and entry-capacity boundaries, Python/Rust dashboard HTML
comparisons, and the existing evaluation, API, CLI, and safety suites. The
Rust storage concurrency test and full Rust workspace test suite were run
separately. Five skips are environment-dependent; Windows and macOS results
come from hosted CI. Coverage does not replace the mutation, cross-platform,
security, parity, or frozen release-evaluation gates.
