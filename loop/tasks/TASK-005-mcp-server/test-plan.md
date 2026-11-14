# Test-first contract — TASK-005

- safety: TOOLS names == {route,classify,explain,list_models,list_hosts}; no exec/run.
- build_server registers exactly those 5 tools.
- route returns a plan + decision_id, no execution.
- classify returns dimensions; explain roundtrips a routed id; unknown id -> None.
- list_models/list_hosts return structured data.
- `agentrouter mcp --help` resolves without invoking the runtime.
Regression: full pytest green (425).
