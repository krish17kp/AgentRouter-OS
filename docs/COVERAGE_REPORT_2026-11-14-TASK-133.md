# Coverage report — TASK-133

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `CARGO_TARGET_DIR=/data/agentrouter-rust-next-target ./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,525 passed; 5 skipped; 0 failed.
- Runtime: 332.46 seconds.
- Statement coverage: 91.970% (6,895 of 7,497 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,854 covered statement/branch items of 9,731).
- The 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.

The suite includes direct Python/Rust differentials for every public model,
validator, enum and derived property in `agentrouter/schema.py`. It covers
required fields and omitted defaults, Classification optionals, coercions,
constraints, unknown-field rejection, and nested model values. The schema
module itself has 100% statement and branch coverage.

Combined coverage is the weighted ratio of covered statements plus covered
branch arcs to all statements plus branch arcs.
