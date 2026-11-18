# TASK-255 — Doctor bundle error parity

## Objective

Preserve Python's actionable error prefix when Rust `doctor --bundle` cannot
create a diagnostic bundle.

## Evidence

- Rust bundle failures now begin with `Could not write the bundle:` and retain
  exit code 2.
- Existing bundle safety and diagnostics compatibility tests pass 45 cases;
  the Rust CLI crate passes 89 tests with strict Clippy and formatting.
