# TASK-150 — Preserve API response integer parity

## Goal

Keep Rust `ModelSummary.context_window` compatible with Python's unbounded
Pydantic integer field.

## Scope

- Deserialize response `context_window` values with the shared Pydantic integer
  coercion and preserve them as arbitrary-precision JSON integers.
- Compare large positive and negative integers, integer strings, booleans, and
  invalid values against `agentrouter.server.schemas.ModelSummary`.
- Keep the API schema module Partial until the full public model and FastAPI
  behavior is covered.

## Acceptance

- Rust response JSON matches Pydantic for accepted integer inputs beyond the
  signed 64-bit range.
- Rust rejects the same invalid integer inputs as Pydantic.
- No unrelated response fields or release thresholds change.
