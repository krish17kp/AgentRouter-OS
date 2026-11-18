# TASK-245 — Core CLI help parity

## Objective

Align Rust unified help handling for the core inspection command groups with
Python's Typer surface.

## Evidence

- `models list --help`, `hosts doctor --help`, `providers status --help`, and
  `registry list --help`, plus provider refresh/rollback/restore help
  now succeed with exit 0 and usage text.
- Route/unified compatibility selection passes 65 tests.
- Formatting and diff checks pass; the Rust CLI crate remains covered by its
  89-test and strict-Clippy checks.
