# Implementation log — TASK-005

## Files changed
- NEW agentrouter/mcp_server.py (tools + build_server + main; lazy mcp import).
- agentrouter/cli.py: `mcp` command (guarded).
- pyproject.toml: `[mcp]` extra + README "MCP server" section.
- NEW tests/test_mcp_server.py (7 tests).

## Decisions (ponytail)
- Thin adapter over service.py -> zero duplicated routing logic.
- Read/route/explain surface only; execute deliberately excluded (safety).
- mcp optional extra + lazy import -> core package never hard-depends on mcp.

## Verify: pytest 425 passed; ruff clean; bandit 0. mcp 1.28.1 installs cleanly on this env.
