# Coverage report — TASK-140

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3; MCP Python SDK: 2.3.0

## Full regression

Command: `./.venv/bin/python -m pytest -q --cov=agentrouter --cov-branch`

- 2,538 passed; 5 skipped; 0 failed.
- Runtime: 468.91 seconds, including the reserved-port Windows fixture repair.
- Statement coverage: 92.025% (6,900 of 7,498 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 91.030% (8,859 covered statement/branch items of 9,732).
- The 90% statement and 85% branch thresholds pass.
- `agentrouter/sdk.py` remains at 100% statement and branch coverage.

TASK-140 adds three Python/Rust SDK differential variants for authenticated,
absent, and blank API keys. The full suite increases by six tests from TASK-137;
the SDK coverage was already complete and remains at 100%.
