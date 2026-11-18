# TASK-195 evidence

Date: 2026-11-17

Using `/data/agentrouter-build/target/release/agentrouter` and a fresh
temporary `AGENTROUTER_HOME`/plugin root:

```console
agentrouter init
agentrouter route 'summarize a support ticket' --json
agentrouter doctor --json
# init=ok route=ok doctor=ok
agentrouter --version
# agentrouter 0.5.0rc1
```

The same isolated binary completed MCP stdio negotiation for protocol
`2025-11-25`; `tools/list` returned exactly five safe tools.
