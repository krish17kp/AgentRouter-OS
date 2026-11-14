# Coverage report — TASK-128

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,382 passed; 4 skipped; 0 failed.
- Runtime: 343.57 seconds.
- Statement coverage: 91.983% (6,896 of 7,497 statements).
- Branch coverage: 87.735% (1,960 of 2,234 branches).
- Combined coverage: 91.008% (8,856 covered statement/branch items of 9,731).
- The unchanged 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.

Combined coverage is the weighted ratio of covered statements plus covered
branch arcs to all statements plus branch arcs. This is local Linux evidence;
hosted cross-platform Rust and Python/Rust validation is tracked separately in
`PRODUCTION_STATUS.md`.
