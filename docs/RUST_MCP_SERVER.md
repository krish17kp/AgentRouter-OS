# AgentRouter MCP servers

AgentRouter exposes five planning tools through MCP: `route`, `classify`,
`explain`, `list_models`, and `list_hosts`. The server does not offer a tool
that executes a process or calls a model. Routing may write a local decision
record; all provider and command execution remains outside this MCP surface.

## Protocol support

The Rust stdio server and the Python SDK 2.x server speak the current
`2026-07-28` stateless protocol. They answer `server/discover`, advertise that
modern version, validate per-request protocol metadata, and include server
identity in result metadata. A request for an unsupported modern version gets
the protocol-defined `-32022` response with the supported version list.

Both servers retain legacy `initialize` negotiation through `2025-11-25` for
older hosts. The Python MCP SDK 2.x requires Python 3.11 or later, so the
optional `mcp` extra selects SDK 1.x for Python 3.10 and SDK 2.x for Python
3.11+. Python 3.10 therefore remains supported with the legacy MCP protocol.

The Rust unified CLI dispatches `agentrouter mcp` to the Rust stdio server. The
Python `agentrouter mcp` command continues to run the official Python SDK as
the release reference while the rest of the Rust migration remains incomplete.

## Run locally

Initialize the registry with the normal Python CLI, then start the Rust stdio
process from the repository checkout:

```bash
agentrouter init
cargo run --locked -p agentrouter-mcp --bin agentrouter-mcp-server -- \
  --home "$HOME/.agentrouter"
```

The process uses newline-delimited JSON-RPC over stdin and stdout. Standard
output is reserved for protocol messages; diagnostics go to stderr. Frames
are limited to 4 MiB and oversized frames are drained without growing the
frame buffer beyond that limit. Service errors do not expose internal paths,
provider messages, or credentials.

The tool schemas are stored in
[`contracts/mcp/tools.json`](../contracts/mcp/tools.json) and are checked
against the Python SDK's generated definitions.

## Compatibility checks

`tests/test_rust_mcp_compat.py` uses the official Python MCP SDK 2.3 client to
compare modern `auto` discovery and explicit legacy negotiation against both
Python and Rust stdio servers. It checks negotiated versions, advertised
capabilities, server identity, schemas, structured results for all five tools,
and unknown-tool errors. SDK 1.x continues to use the same legacy check on
Python 3.10. `tests/test_rust_unified_cli_compat.py` checks both the Rust CLI
dispatch and direct legacy stdio use. CI runs the compatibility suite on
Linux, Windows, and macOS.

## Protocol references

- [MCP 2026-07-28 versioning and compatibility](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/versioning.mdx)
- [MCP `server/discover` request and result](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/discover.mdx)
- [Official Python SDK v2 release and v1 maintenance notice](https://github.com/modelcontextprotocol/python-sdk/releases)
- [Official Python SDK v1-to-v2 migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)
