# Coverage report — TASK-125

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3

## Full regression

Command: `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,332 passed; 4 skipped; 0 failed.
- Runtime: 403.50 seconds.
- Statement coverage: 91.983% (6,896 of 7,497 statements).
- Branch coverage: 87.735% (1,960 of 2,234 branches).
- Combined coverage: 91.008%.
- The unchanged release thresholds of 90% statement and 85% branch coverage pass.
- One upstream Starlette deprecation warning was emitted by the test client; it did not affect the result.

This run includes the local TASK-125 Rust registry deserialization fix. Hosted
cross-platform validation of that fix is still pending. The report describes
local Linux coverage and does not claim Windows or macOS Python coverage.
