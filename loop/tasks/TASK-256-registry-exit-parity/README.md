# TASK-256 — Registry-backed CLI exit parity

## Objective

Ensure unified Rust inspection commands return Python's registry failure exit
code when the configured home has no readable registry.

## Evidence

- `hosts list/show` and `models list/show` now print the registry error and exit
  3 instead of being treated as generic usage failures (exit 2).
- Four process-level regressions cover the missing-home contract.
- The focused unified test selection passes 5 cases and strict Clippy passes.
