# Coverage report — TASK-127

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,378 passed; 4 skipped; 0 failed.
- Runtime: 285.82 seconds.
- Statement coverage: 91.970% (6,895 of 7,497 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988%.
- The unchanged 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.

This is local Linux evidence for the arbitrary-precision Rust schema, classifier,
routing, and HTTP compatibility changes. Hosted cross-platform validation is
pending the next RC push.
