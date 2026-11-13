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
| Python regression | 2,048 passed, 5 skipped |
| Line coverage | 92.49% (6,628 / 7,166 statements) |
| Branch coverage | 87.61% (1,845 / 2,106 branch outcomes) |
| Combined coverage reported by pytest-cov | 91.38% |
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
The release suite also exercises the Rust HTTP request/response schemas against
Pydantic for request bounds, supported scalar coercions, typed response fields,
defaults, unknown-field handling, and passthrough of stored engine response
fields. Forty-three Python/Rust service differential cases cover model/host
listing, classification, route previews and persistence, stored decisions,
feedback, and dry-run behavior. Live Rust HTTP process checks cover routes,
auth/CORS, request IDs, rate limiting, replay, and exact Python/Rust response
parity for model/host listing, classification, and route preview. The full
unbounded Python integer range and some FastAPI lifecycle and docs behavior
remain partial. HTTP validation errors now compare field-specific FastAPI
messages for 21 invalid payloads, malformed JSON, and unknown routes. Rust
fixed-window rate limiting, idempotency cache expiry, and
response replay fields are also compared with the Python server primitives.
Catalog operation checks compare provenance, freshness summaries, sorted
generated-catalog listing, deprecations, and rollback/restore against Python;
Rust safety checks cover linked paths and no-clobber restoration. The Rust SDK
has local HTTP fixture tests for request cleanup, API-key handling, API errors,
and redirect refusal. Classification schema tests compare Python/Rust JSON
round-tripping and rejection of unknown fields.
The candidate package version is `0.5.0rc1`. The five skips are
environment-dependent; CI is responsible for Windows and macOS confirmation.
Coverage does not replace mutation, security, parity, or release-evaluation
gates.

This run includes two Python SDK end-to-end checks against the Rust HTTP
process, covering persisted and no-log routing, feedback, decision lookup,
dry-run, API-key authentication, and typed errors. It also includes the MCP
stdio parity check against the Python FastMCP 1.30.0 server for negotiated
protocol version, capabilities, all five tool schemas, and structured outputs.
The Rust provider-refresh slice is checked against Python for all OpenAI
family prefixes, OpenRouter model metadata and price tiers, offline payload
filtering, and skipped-entry warnings.
Reliability checks compare load and soak result schemas, run the Rust load
runner against a live Python loopback server, confirm unique request IDs, and
verify redirect refusal without timing thresholds.
The legacy gold evaluator comparison covers the full classifier fixture,
all synthetic routing scenarios, parsed JSON reports, and byte-identical
Markdown and CSV artifacts.
