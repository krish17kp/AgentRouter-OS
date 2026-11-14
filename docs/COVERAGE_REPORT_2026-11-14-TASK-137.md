# Coverage report — TASK-137

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3; MCP Python SDK: 2.3.0

## Full regression

Command: `./.venv/bin/python -m pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,532 passed; 5 skipped; 0 failed.
- Runtime: 419.96 seconds.
- Statement coverage: 91.971% (6,896 of 7,498 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,855 covered statement/branch items of 9,732).
- The 90% statement and 85% branch thresholds pass.
- `agentrouter/mcp_server.py` remains at 100% statement and branch coverage.

TASK-136 and TASK-137 add three Rust reliability integration tests: managed
loopback startup/shutdown, an initialized-home soak run with credential
isolation and report output, and safe failure when the requested home is a
regular file. The Python production sources did not change, so coverage matches
the TASK-135 report while the full passing test count increased by three.
