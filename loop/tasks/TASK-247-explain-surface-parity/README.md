# TASK-247 — Explain surface parity

## Objective

Align the unified Rust stored-decision command with Python's public `explain`
surface instead of always emitting JSON.

## Evidence

- `agentrouter explain <decision-id>` now renders the task, classification,
  eligibility, score table, weights, shifts, and safety gate in text form.
- `agentrouter explain <decision-id> --json` preserves the structured decision
  payload and forwards the JSON option to the Rust decision probe.
- The focused unified CLI compatibility selection passes 36 tests; the Rust
  CLI crate passes 89 tests with strict Clippy and formatting.
- The release gate remains unchanged and is still governed by the frozen
  context-band evaluation and owner-controlled review steps.
