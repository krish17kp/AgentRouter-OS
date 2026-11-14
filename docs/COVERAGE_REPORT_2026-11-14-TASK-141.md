# Coverage report — TASK-141

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3; MCP Python SDK: 2.3.0

## Full regression

Command: `./.venv/bin/python -m pytest -q --cov=agentrouter --cov-branch --cov-report=term-missing:skip-covered --cov-report=json:/tmp/agentrouter-task141-coverage.json`

- 2,550 passed; 5 skipped; 0 failed.
- Runtime: 408.95 seconds.
- Statement coverage: 92.025% (6,900 of 7,498 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 91.030% (8,859 covered statement/branch items of 9,732).
- The 90% statement and 85% branch thresholds pass.
- `agentrouter/sdk.py` remains at 100% statement and branch coverage.

TASK-141 adds deterministic malformed-fixture rejection, native unsupported
protocol parity, and credential-safe fixture logging. Coverage totals are
unchanged because these tests exercise the Rust bridge and SDK contract without
adding uncovered Python product paths. This report supersedes the TASK-140
full-suite count.
