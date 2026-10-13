# Plan — TASK-005 MCP server (L2)

## Design (ponytail, reuse service.py)
- NEW agentrouter/mcp_server.py: plain tool callables route/classify/explain/list_models/
  list_hosts that delegate to agentrouter.server.service. build_server() registers them on
  FastMCP (lazy `mcp` import). main() runs stdio.
- Safety: read/route/explain ONLY. NO execute tool (service.execute_dry_run is NOT exposed).
- CLI: `agentrouter mcp` (guarded; clear error if [mcp] extra missing).
- pyproject: optional `mcp = ["mcp>=1.2"]` extra; core import unaffected.

## Tests
Tool callables tested directly (no MCP runtime); safety invariant (no exec tool);
build_server registers exactly 5 tools; explain roundtrip + unknown-id None; CLI --help.

## Risk: medium (agent-facing surface) -> security review required.
