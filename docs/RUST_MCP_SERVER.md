# Rust MCP server migration preview

The Rust MCP process is a parity preview for the supported Python `agentrouter mcp`
command. Python remains the supported release entry point until Rust CLI
integration and the complete MCP contract pass the migration gates.

## Run locally

Initialize the registry with the normal Python CLI, then start the Rust stdio
process from the repository checkout:

```bash
agentrouter init
cargo run --locked -p agentrouter-mcp --bin agentrouter-mcp-server -- \
  --home "$HOME/.agentrouter"
```

The process speaks newline-delimited JSON-RPC over stdin and stdout. Standard
output is reserved for protocol messages; diagnostics go to stderr. Frames are
limited to 4 MiB and oversized frames are drained without growing the frame
buffer beyond that limit.

The server exposes the Python tools `route`, `classify`, `explain`,
`list_models`, and `list_hosts`. Routing is dry-run only; there is no process
execution tool. The tool schemas are checked into
[`contracts/mcp/v1/tools.json`](../contracts/mcp/v1/tools.json), generated from
the Python FastMCP 1.30.0 contract used by the parity test.

## Compatibility checks

`tests/test_rust_mcp_compat.py` uses the official Python MCP client to compare
negotiated protocol version, capabilities, schemas, and structured results for
all five tools against the Python server. Unknown tools must fail as tool
errors. CI pins the MCP SDK version that generated the checked-in schema and
runs this check on Linux, Windows, and macOS.

The Rust server is not yet dispatched through `agentrouter mcp`; Python remains
the functional and release authority while the broader lifecycle, error, and
CLI parity audit continues.
