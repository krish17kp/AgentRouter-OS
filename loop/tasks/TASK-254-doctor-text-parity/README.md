# TASK-254 — Doctor human-readable output parity

## Objective

Align Rust `doctor` text output with Python's public summary, remedy
indentation, pluralization, and next-step wording while preserving JSON output.

## Evidence

- Remedy lines now use Python's nine-space indentation.
- Failure summaries include the first actionable remedy; warning and clear
  summaries use Python's pluralization and next-step text.
- The focused diagnostics compatibility suite passes 18 tests; the Rust CLI
  crate passes 89 tests with strict Clippy and formatting.
