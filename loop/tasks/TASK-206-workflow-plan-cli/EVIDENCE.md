# TASK-206 evidence

Date: 2026-11-17

The unified Rust binary now exposes `workflow plan`. It accepts a JSON array or
object with a `steps` array from stdin, supports bounded step/cost budgets and
an explicit tool allowlist, and emits a deterministic planning-only result.

```console
printf '%s\n' '{"steps":[{"id":"prepare","estimated_cost":2},{"id":"write","depends_on":["prepare"],"side_effect_key":"file:report","idempotency_key":"report-v1","estimated_cost":3}]}' \
  | cargo run --quiet --locked -p agentrouter-cli --bin agentrouter -- workflow plan --json
# ordered_steps=[prepare, write], estimated_cost=5, execution_enabled=false

printf '%s\n' '{"steps":[{"id":"a","estimated_cost":1},{"id":"b","depends_on":["a","a"],"estimated_cost":1}]}' \
  | cargo run --quiet --locked -p agentrouter-cli --bin agentrouter -- workflow plan --json
# exit 2: duplicate dependency is rejected
```

The complete unified CLI compatibility file passes, including the workflow
planning/tool-policy regression and the existing read-only execution-plan
regression:

```console
uv run --with '.[dev,server,security]' pytest -q tests/test_rust_unified_cli_compat.py
# 17 passed in 5.87s
```

The planner remains read-only; no agent, provider, tool, or workspace was
started or changed.
