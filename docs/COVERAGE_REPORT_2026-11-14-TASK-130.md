# Coverage report — TASK-130

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,405 passed; 4 skipped; 0 failed.
- Runtime: 416.38 seconds.
- Statement coverage: 91.970% (6,895 of 7,497 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,854 covered statement/branch items of 9,731).
- The unchanged 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.

Combined coverage is the weighted ratio of covered statements plus covered
branch arcs to all statements plus branch arcs. This run includes TASK-130's
direct Python/Rust probes for `Provider` and `ExecutionTarget`.
