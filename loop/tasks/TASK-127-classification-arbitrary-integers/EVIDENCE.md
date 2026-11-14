# TASK-127 evidence

## Reproduced gaps

- Python accepts negative and arbitrarily large integer `Classification`
  values; Rust previously used `u32`, rejecting negatives and values above the
  32-bit boundary.
- Python accepts booleans, integral floats, integer strings, underscore
  separators, and integral decimal strings on the Pydantic model. Rust's
  derived `u32` deserializer did not match those forms.
- The Rust classifier saturated inferred token counts at `u32::MAX`, and the
  API rejected valid positive request values above the Rust classifier range.

## Implementation

Rust `Classification.context_tokens` now uses arbitrary-precision
`serde_json::Number`, backed by a shared Pydantic-compatible integer coercer.
Classifier estimates and overrides preserve exact values. Routing capacity
checks compare without truncation; API validation, service calls, MCP, and the
Rust SDK use the same representation.

## Verification

- Focused Python/Rust Classification, classifier, and HTTP schema/service
  differential run: 295 passed. The full regression below includes the final
  invalid-string cases and all Rust routing unit tests.
- `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term` —
  2,378 passed, 4 skipped, 0 failed in 285.82 seconds; statement coverage
  91.970% (6,895/7,497), branch coverage 87.690% (1,959/2,234), combined
  coverage 90.988%.
- `cargo test --workspace --locked` — passed across all crates and doc tests.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D
  warnings` — passed.
- `cargo fmt --all -- --check`, `ruff check`, `ruff format --check`, Bandit,
  pip-audit, cargo audit, and `git diff --check` — passed.
- `cargo check --workspace --all-targets --locked`: passed.
- Hosted cross-platform checks are pending the next authorized RC push.
