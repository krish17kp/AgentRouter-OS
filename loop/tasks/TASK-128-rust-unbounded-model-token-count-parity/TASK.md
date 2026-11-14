# TASK-128 — Rust unbounded model token-count parity

## Objective

Make Rust `ModelEntry.context_window`, `max_input_tokens`, and
`max_output_tokens` match Python's unbounded positive integer fields, and carry
those values through routing, registry refresh, serialization, and display.

## Scope

- Preserve exact arbitrary-precision integer values and Pydantic-compatible
  coercions, including large integer YAML scalars that the YAML value parser
  cannot represent directly.
- Keep invalid values fail-closed and preserve Pydantic's narrower conversion
  range for integral floating-point inputs.
- Preserve exact OpenRouter refresh context and completion-token counts and
  derive the default output limit with integer floor division.
- Compare model capacity and context-fit thresholds without narrowing. Match
  Python's rounded integer-division behavior at the 2x and 16x score cutoffs.
- Keep CLI model display grouped, preserve HTTP/JSON number shapes, and cap the
  OpenAI adapter's outgoing output limit at its existing 4,096-token bound.

## Verification

The complete Python coverage run, Rust workspace tests, strict Clippy, Rust
1.89 minimum check, formatting, security audits, and hosted cross-platform
checks are recorded in `EVIDENCE.md` after the final run.

## Status limits

This closes the Rust width mismatch for model token-count fields. It does not
complete `agentrouter/schema.py` or the entire Rust migration. The frozen
context-band release gate remains unchanged and requires real human labels.
