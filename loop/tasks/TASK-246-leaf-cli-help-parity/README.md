# TASK-246 — Leaf CLI help parity

## Objective

Align the Rust unified command's successful `--help` behavior with the
existing Python CLI for the remaining leaf command paths.

## Evidence

- `init`, `explain`, `feedback`, `stats`, `prompt`, `doctor`, and `dashboard`
  now return exit 0 with usage text when invoked with `--help`.
- The focused route/unified compatibility selection passes 72 tests (37 direct
  route cases plus the unified CLI selection).
- `cargo test --locked -p agentrouter-cli` passes 89 tests; strict Clippy,
  formatting, and `git diff --check` pass.
- The canonical evaluation gate remains unchanged at 165 cases and 98.23/100;
  `context_band_accuracy=0.6667` remains below the required 0.90 threshold.
