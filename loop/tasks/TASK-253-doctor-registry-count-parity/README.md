# TASK-253 — Doctor registry-count parity

## Objective

Correct the Python diagnostic's registry model count and verify that the Rust
and Python doctors report the same initialized registry summary.

## Evidence

- Python `diagnostics.check_registry` now unpacks `load_models()` and reports
  the actual model count instead of the tuple length (`2`).
- The initialized-home Python/Rust differential now compares the complete
  `registry.load` check.
- Focused diagnostics compatibility passes 17 tests; the full Rust/Python
  compatibility selection remains green after the change.
