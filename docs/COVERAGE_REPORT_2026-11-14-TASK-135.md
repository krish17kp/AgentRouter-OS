# Coverage report — TASK-135

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3; MCP Python SDK: 2.3.0

## Full regression

Command: `./.venv/bin/python -m pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,529 passed; 5 skipped; 0 failed.
- Runtime: 409.36 seconds.
- Statement coverage: 91.971% (6,896 of 7,498 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,855 covered statement/branch items of 9,732).
- The 90% statement and 85% branch thresholds pass.
- `agentrouter/mcp_server.py` remains at 100% statement and branch coverage.
- TASK-135 adds four parameterized Python/Rust concurrency scenarios for
  same-key successes, non-2xx responses, failures, and separate keys.

The increased test count does not change Python production-source coverage from
TASK-134. The Rust workspace, strict Clippy, format, Ruff, and the focused
8-case server-limits compatibility suite pass separately.
