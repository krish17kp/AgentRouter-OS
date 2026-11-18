# TASK-187 evidence

Date: 2026-11-17

```console
uv build
uv run --isolated --with ./dist/agentrouter_os-0.5.0rc1-py3-none-any.whl agentrouter --version
AGENTROUTER_HOME=<fresh-temp-home> uv run --isolated --with ./dist/agentrouter_os-0.5.0rc1-py3-none-any.whl agentrouter init
AGENTROUTER_HOME=<same-home> uv run --isolated --with ./dist/agentrouter_os-0.5.0rc1-py3-none-any.whl agentrouter route 'summarize a support ticket' --json
```

The sdist and wheel were built successfully. The isolated wheel reported
`agentrouter-os 0.5.0rc1`; installed `init` created the seed registry and
SQLite home; installed `route --json` returned a decision record. `uv` emitted
only its existing dependency-specifier normalization warning for a transitive
metadata entry.
