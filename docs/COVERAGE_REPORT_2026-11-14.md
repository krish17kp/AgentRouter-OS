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
| Python regression | 2,180 passed, 5 skipped |
| Line coverage | 92.70% (6,704 / 7,232 statements) |
| Branch coverage | 88.12% (1,884 / 2,138 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.65% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the release-candidate worktree. It
includes simultaneous Python SQLite schema-migration checks, idempotency cache
capacity boundaries, portable JSON integer and non-finite-number validation,
Python/Rust storage round trips and snapshots, Python/Rust dashboard HTML,
OpenAPI canonicalization, and baseline-trust comparisons, plus the existing
evaluation, API, CLI, and safety suites. Rust
workspace tests and strict Clippy were run separately. This run adds thirty-four
Python/Rust OpenAPI surface-diff cases for version/server/path/method changes,
operation metadata and authentication, parameter presence/requiredness,
request/response media types, body requiredness, response statuses, and
documented semantics; inline schema coverage now includes type, field presence
and requiredness, array items, enum/const, bounds, patterns, formats, defaults,
and `additionalProperties`. The Rust slice is not the full compatibility
analyzer.
Five skips are
environment-dependent; Windows and macOS results come from hosted CI. Coverage
does not replace mutation, cross-platform, security, parity, or frozen
release-evaluation gates.
