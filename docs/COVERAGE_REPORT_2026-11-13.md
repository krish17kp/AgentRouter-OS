# Python coverage report — 2026-11-13

## Reproduction

Run from the repository root so coverage measures the checked-out source tree:

```console
uv sync --extra dev --extra server --extra property --extra mcp
uv run pytest -q --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:coverage.json
```

## Result

| Measure | Result |
|---|---:|
| Python regression | 1,973 passed, 4 skipped |
| Line coverage | 92.45% (6,625 / 7,166 statements) |
| Branch coverage | 87.56% (1,844 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.34% |
| Project line / branch thresholds | 90% / 85% — both passed |
| CI total-coverage threshold | 80% — passed |
| Warnings | 1 Starlette/httpx deprecation warning |

Run used Python 3.12.15 on Linux against the release-candidate worktree.
It includes the Rust feedback-learning and evaluation crates; external
evaluation adapter and annotation differential checks; Python/Rust parity for
the evaluation scorecard, registered-fixture runner, context bands, report
artifacts, and annotation schema. The schema checks include Pydantic-compatible
boolean and integer coercion, underscore-separated and integral-decimal
integer strings, underscore datetime separators, numeric Unix timestamp
rounding, leap-second rejection, and invalid-input rejection. An additional
40-value Python/Rust timestamp corpus has no output or acceptance mismatch.
The release suite also exercises the new Rust HTTP request-schema crate against
Pydantic for supported bounds, defaults, and unknown-field behavior. Scalar
coercion, response passthrough types, middleware, and the Rust server lifecycle
remain partial. The release suite also exercises Rust fixed-window rate limiting,
idempotency cache expiry, and response replay fields against the Python server
primitives.
Catalog operation checks compare provenance, freshness summaries, sorted
generated-catalog listing, deprecations, and rollback/restore against Python;
Rust safety checks cover linked paths and no-clobber restoration. The Rust SDK
has local HTTP fixture tests for request cleanup, API-key handling, API errors,
and redirect refusal. Classification schema tests compare Python/Rust JSON
round-tripping and rejection of unknown fields.
The candidate package version is `0.5.0rc1`. The four skips are
environment-dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation
gates.
