# Coverage report — TASK-147

Run date: 2026-11-14

Platform: Linux, Python 3.12

Pytest: 9.0.3; Coverage.py: 7.17.3

## Full regression

Command: `./.venv/bin/python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term`

- 2,570 passed; 5 skipped; 0 failed.
- Runtime: 256.87 seconds.
- Statement coverage: 92.030% (6,905 of 7,503 statements).
- Branch coverage: 87.712% (1,963 of 2,238 branches).
- Combined coverage: 91.038% (8,868 covered statement/branch items of 9,741).
- The 90% statement and 85% branch thresholds pass.
- `agentrouter/openai_adapter.py` remains at 100% statement and branch coverage.

This refresh includes the OpenAI missing, malformed, and non-2xx HTTP status
regressions from TASK-146 and the Rust SDK connection-timeout slice from
TASK-147. It supersedes the TASK-141 coverage totals.
