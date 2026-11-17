# TASK-249 — Task-based prompt parity

## Objective

Support Python's `prompt generate TASK` path in the unified Rust CLI while
retaining the stored-decision path.

## Evidence

- Unified Rust classifies and routes task text through the existing Rust
  pipeline, then generates the same execution prompt as Python.
- Task-based stdout preserves Python's trailing newline behavior and supports
  the same `--tool` and `--out PATH` options.
- The focused decision/unified CLI selection passes 43 tests; the Rust CLI
  crate remains green at 89 tests with strict Clippy and formatting.
- Execution remains prompt generation only; no provider or agent is invoked.
