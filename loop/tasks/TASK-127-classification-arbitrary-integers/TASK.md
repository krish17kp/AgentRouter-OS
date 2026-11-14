# TASK-127 — Classification arbitrary-precision integers

## Objective

Match Python/Pydantic integer behavior for `Classification.context_tokens` and
preserve the exact value throughout Rust classification and routing.

## Scope

- Deserialize and serialize signed arbitrary-precision `context_tokens` values,
  including Pydantic integer coercion for booleans, integral floats, numeric
  strings, digit separators, and integral decimal strings.
- Keep Rust text-based token estimation exact beyond `u32` and `u64` rather than
  saturating or wrapping.
- Carry the value through classifier overrides, model-capacity eligibility,
  HTTP request validation/service handling, MCP classification, and the Rust
  SDK.
- Keep context-band boundaries and routing comparisons consistent for large
  positive and negative integers.

## Verification

- Focused Python/Rust Classification, classifier, and HTTP schema/service
  differentials: 295 passed; the full run includes all final regression cases.
- Full Python suite: 2,378 passed, 4 skipped; 91.970% statement coverage,
  87.690% branch coverage, 90.988% combined coverage.
- Full Rust workspace and strict Clippy pass locally.
- Rust format, Ruff check/format, Bandit, pip-audit, cargo audit, and diff
  checks pass locally.
- Hosted cross-platform validation is pending the next authorized RC push.

## Status limits

This task closes the `Classification.context_tokens` width/coercion gap. It
does not claim full `agentrouter/schema.py` module parity or release readiness;
the frozen context-band release gate remains independent and unchanged.
