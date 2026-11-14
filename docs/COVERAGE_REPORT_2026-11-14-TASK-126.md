# Coverage report — TASK-126

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,352 passed; 4 skipped; 0 failed.
- Runtime: 384.19 seconds.
- Statement coverage: 91.970% (6,895 of 7,497 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988%.
- The unchanged 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect the result.

This is local Linux evidence for the Rust schema and registry changes. The
previous pushed candidate's platform checks passed, but hosted revalidation of
the latest local changes is still pending.
