# TASK-134 — Current MCP SDK and protocol compatibility

## Objective

Bring the Python and Rust stdio MCP servers forward to the current supported
MCP SDK/protocol while preserving legacy clients, Python 3.10 support, and the
planning-only safety boundary.

## Scope

- Use MCP SDK 2.x on Python 3.11+ and retain MCP SDK 1.x for Python 3.10.
- Implement current stateless discovery, per-request protocol validation,
  modern server identity metadata, and the protocol's unsupported-version
  response in Rust.
- Preserve the legacy `initialize` path and reject modern use of removed
  methods.
- Keep the five safe tools, with no command or model execution tool.
- Verify both SDK/protocol paths locally and in continuous integration.
