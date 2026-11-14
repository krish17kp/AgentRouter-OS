# Coverage report — TASK-134

Run date: 2026-11-14

Platform: Linux, Python 3.12.15

Pytest: 9.0.3; MCP Python SDK: 2.3.0

## Full regression

Command: `CARGO_TARGET_DIR=/data/agentrouter-rust-next-target ./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term`

- 2,525 passed; 5 skipped; 0 failed.
- Runtime: 317.45 seconds.
- Statement coverage: 91.971% (6,896 of 7,498 statements).
- Branch coverage: 87.690% (1,959 of 2,234 branches).
- Combined coverage: 90.988% (8,855 covered statement/branch items of 9,732).
- The 90% statement and 85% branch thresholds pass.
- One Starlette test-client deprecation warning was emitted; it did not affect
  the result.
- `agentrouter/mcp_server.py` has 100% statement and branch coverage.

MCP-focused compatibility tests pass on Python 3.10 with MCP 1.30.0 and Python
3.11/3.12 with MCP 2.3.0. They exercise modern stateless discovery, legacy
initialization, tool schemas/results, unknown-tool errors, and the Rust unified
CLI. Full Rust workspace tests and strict Clippy pass separately.

Combined coverage is the weighted ratio of covered statements plus covered
branch arcs to all statements plus branch arcs. The Cargo target cache was
placed on `/data` for this run to avoid the local temporary-filesystem quota.
