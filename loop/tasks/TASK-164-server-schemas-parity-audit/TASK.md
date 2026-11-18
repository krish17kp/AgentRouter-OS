# TASK-164 — Server schemas full-module parity audit

Audit all request and response models, constants, defaults, coercions, bounds,
extra-field policy, inheritance, passthrough keys, serialization, malformed
envelopes, and Unicode length semantics in `agentrouter.server.schemas` against
`agentrouter-api::{schemas,responses}`. Promote only after independent review
and exhaustive differential evidence.

## Evidence

- Restored the public `MAX_TOOL_NAME_CHARS` constant in Rust and exposed a
  machine-readable constant manifest for direct Python/Rust comparison.
- Added differential coverage for request defaults; owned-response required
  fields and types; passthrough defaults and unknown nested values; nullable and
  malformed `risk`/`tools`; and exact/max+1 non-BMP Unicode boundaries for task,
  prefer, note, and both decision-id request models.
- `tests/test_rust_http_schemas_compat.py`: 93 passed.
- `cargo test -p agentrouter-api --locked`: passed.
- `cargo clippy -p agentrouter-api --all-targets --locked -- -D warnings`: passed.
- Ruff check and format check: passed.
- Full Python regression: 2,696 passed, 7 skipped in 346.49 seconds.
- Independent audit initially requested Unicode and malformed nullable evidence;
  the repair was re-reviewed and explicitly cleared for promotion.

## Decision

Promote `agentrouter/server/schemas.py` from Partial to Parity. HTTP server
lifecycle and service orchestration remain separate Partial rows.
