# Rust R4 registry inspection — 2026-11-10

## Scope and review

- Added a Rust `registry list` probe with JSON/table output, provider and
  active filters, and fail-closed option/registry errors.
- Added the probe to the non-skipping Rust Linux/Windows compatibility job.
- Independent review reproduced malformed model fields accepted by Rust but
  rejected by Python. The shared Rust loader now validates positive token
  sizes, ability scores 0–10, finite non-negative prices, finite ability
  confidence 0–1, and ISO date fields before any CLI or router receives them.

## Evidence

- `tests/test_cli_registry_rust_compat.py`: 19 passing differential cases.
- Rust 1.75 workspace tests, Clippy with warnings denied, formatting: pass.
- Ruff and `git diff --check`: pass.
- Full Python regression: 1,357 passed, 3 skipped, 1 warning.
- Pushed parent `eda4c7a` passed all GitHub workflows, including mutation
  (0.9837 overall, 0.9844 safety/policy/execution, 0 unreviewed survivors).
  The new registry slice needs its own remote CI verdict.

## Release status

Python remains the shipping implementation; Rust R4 is partial and R5–R13
remain open. Canonical context-band accuracy is 0.6667 < unchanged 0.90;
the two-human annotation/adjudication round remains external. No paid
provider request or production deployment was made.
