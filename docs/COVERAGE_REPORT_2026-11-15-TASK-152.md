# Coverage report — TASK-152

Run date: 2026-11-15

Platform: Linux, Python 3.12.15

## Full regression

Command: `./.venv/bin/python -m pytest -q --cov=agentrouter --cov-branch --cov-report=json:/tmp/agentrouter-task152-coverage.json`

- 2,590 passed; 5 skipped; 0 failed.
- Runtime: 387.16 seconds.
- Statement coverage: 92.052% (6,926 of 7,524 statements).
- Branch coverage: 87.756% (1,971 of 2,246 branches).
- Combined coverage: 91.064% (8,897 of 9,770 items).
- The unchanged 90% statement and 85% branch thresholds pass.

The run includes Python/Rust observability, request correlation, route logging,
credential redaction, and all existing regressions. The Rust workspace tests,
strict workspace Clippy, Rust formatting, Ruff, wheel and sdist build, and a
clean-wheel CLI/API/MCP/plugin smoke also pass locally. The frozen routing
evaluation remains unchanged and below its separate release threshold.
