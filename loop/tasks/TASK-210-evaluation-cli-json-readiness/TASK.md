# TASK-210 — Evaluation CLI JSON readiness

## Objective

Expose structured Rust evaluation readiness output for automation without
masking unavailable external datasets or changing the shipping Python gate.

## Acceptance

- `agentrouter-evaluate status --json` reports every registered dataset with
  explicit fixture/real availability and a blocker field;
- `agentrouter-evaluate prepare --json` reports `REAL` or
  `SKIPPED_EXTERNAL` records and preserves existing exit semantics;
- human-readable output remains unchanged;
- no fixture is substituted for a missing verified external loader;
- focused compatibility tests, formatting, workspace tests, and strict Clippy
  pass;
- release documentation continues to identify the frozen human-evaluation
  gate and real external loaders as unresolved.
