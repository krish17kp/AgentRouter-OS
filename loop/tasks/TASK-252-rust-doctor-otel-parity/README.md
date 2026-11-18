# TASK-252 — Rust doctor OpenTelemetry status parity

## Objective

Make the Rust diagnostic report expose the same explicit OpenTelemetry opt-in
state as the shared Rust observability implementation, instead of always
reporting OTel as off.

## Evidence

- `agentrouter doctor --json` now reports `OTel on` when
  `AGENTROUTER_OTEL` is truthy.
- Rust diagnostics compatibility passes 16 tests, including the new opt-in
  process regression.
- The `agentrouter-cli` crate passes 89 tests, strict Clippy, and formatting.
- This is a diagnostics parity increment; runtime metadata and broader
  observability lifecycle parity remain partial.
