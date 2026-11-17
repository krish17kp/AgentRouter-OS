# TASK-191 evidence

Date: 2026-11-17

Added a focused Rust MCP regression covering missing required tool arguments,
invalid boolean context-token input, and malformed JSON-RPC requests. Each path
returns a bounded, stable error response and keeps the process alive; no secret
or execution surface is added.

```console
cargo test --locked -p agentrouter-mcp malformed_tool_arguments -- --nocapture
# passed
cargo test --locked -p agentrouter-mcp
# passed
cargo clippy --locked -p agentrouter-mcp --all-targets -- -D warnings
# passed
```
