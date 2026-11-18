# Independent audit — TASK-005

## security-reviewer-arros — PASS (no CRITICAL/HIGH); bandit 0
- NO REMOTE EXECUTION confirmed: TOOLS = read/route/explain only; execute_dry_run and
  save_feedback deliberately NOT exposed; no tool reaches subprocess.
- explain() returns caller's own local store data -> no escalation (local single-user).
- decision_id coerced to int + parameterized SQL -> no injection/path traversal.
- LOW: route() persists per call (unbounded local store) -> acceptable for local stdio.
- No resources/prompts registered -> no filesystem exposure.

## verification-engineer — 4/5 PASS, 1 FAIL (fixed)
- tests pass (425); tool surface read/route/explain only; delegates to service.py; 5 tools
  with signature-derived schemas.
- FAIL crit-4: `import agentrouter.mcp_server` transitively hard-required fastapi via
  server/__init__.py's eager `from .app import app` -> [mcp] extra not self-sufficient.
- Non-blocking: Typer strips `[mcp]` from --help text (pre-existing, affects `server` too).

## Repair applied
- Removed the unused eager re-export from agentrouter/server/__init__.py (nobody imports
  app/create_app via the package; all use the submodule directly). Now `from .server import
  service` is fastapi-free. Regression test: import with fastapi absent.
- Re-verify: 426 passed; MCP imports without fastapi; direct app import still works; ruff clean.
