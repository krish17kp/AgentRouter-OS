# TASK-132 evidence

Run date: 2026-11-14

## Focused checks

- `tests/test_rust_schema_compat.py` and `tests/test_cli_registry_rust_compat.py`:
  211 passed in 34.47 seconds. The direct cases cover normalized defaults,
  populated fields, date values, arbitrarily large token counts, nested
  execution targets, resolved vendor/key/name properties, finite prices and
  confidence, invalid values, unknown fields, and every required field.
- Full Rust workspace tests: passed.
- Strict Clippy: passed.
- Rust formatting, Ruff format/check, and `git diff --check`: passed.

## Full regression and coverage

Platform: Linux, Python 3.12.15; pytest 9.0.3.

- 2,509 passed; 4 skipped; 0 failed.
- Runtime: 474.88 seconds.
- Statement coverage: 91.970% (6,895 of 7,497 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,854 covered statement/branch items of 9,731).
- The unchanged 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.

## Behavior note

Python now explicitly rejects non-finite registry prices and
`ability_confidence`, matching Rust and preventing non-finite metadata from
entering routing. This intentionally tightens the Python validation contract;
ordinary finite values and the documented bounds remain unchanged.

Hosted cross-platform checks for this change are pending its authorized RC
push. The frozen context-band release gate remains unchanged.
