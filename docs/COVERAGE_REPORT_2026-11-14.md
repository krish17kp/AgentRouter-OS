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
| Python regression | 2,211 passed, 5 skipped |
| Statement coverage | 92.83% (6,715 / 7,234 statements) |
| Branch coverage | 88.63% (1,895 / 2,138 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.87% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the release-candidate worktree. It
includes simultaneous Python SQLite schema-migration checks, idempotency cache
capacity boundaries, portable JSON integer and non-finite-number validation,
Python/Rust storage round trips and snapshots, Python/Rust dashboard HTML,
OpenAPI canonicalization, baseline-trust comparisons, and canonical Rust
contract export with provenance and safe-write refusals, plus Rust plugin
inventory, destination-root, portable path-validation, and ownership-record
shape checks, plus the existing evaluation, API, CLI, and safety suites. Rust workspace tests and strict
Clippy were run separately. The contract compatibility suite has 70 Python/Rust
cases in total, including canonicalization, reference validation, and baseline
loading. Surface-diff cases cover version/server/path/method changes, operation
metadata and authentication, parameter presence/requiredness, request/response
media types, body requiredness, response statuses, and documented semantics.
Inline schema coverage now includes type, field presence
and requiredness, array items, enum/const, bounds, patterns, formats, defaults,
and `additionalProperties`, plus matching operation-parameter schemas. Eleven
focused cases exercise nullable wrappers, union branch direction and order,
`$ref` expansion inside union branches, and the shared 64-level expansion
limit. Reference fixtures also cover local aliases, missing targets, recursive
schemas, and sibling behavior. The Rust slice is not the full compatibility
analyzer.
Five skips are
environment-dependent; Windows and macOS results come from hosted CI. Coverage
does not replace mutation, cross-platform, security, parity, or frozen
release-evaluation gates.
