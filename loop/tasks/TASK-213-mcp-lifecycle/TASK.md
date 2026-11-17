# TASK-213 — MCP legacy lifecycle hardening

## Objective

Make the Rust stdio MCP server enforce the legacy initialize lifecycle while
retaining the current stateless modern discovery/request path and the safe
five-tool surface.

## Acceptance

- legacy requests before `initialize` fail closed with the stable not-initialized
  JSON-RPC error;
- successful legacy initialization enables subsequent tools/resources/ping
  requests and preserves negotiated-version behavior;
- modern requests continue to validate per-request protocol metadata without a
  stateful handshake;
- malformed input, oversized frames, notifications, and unknown tools remain
  safe and bounded;
- Rust MCP tests, strict Clippy, and Python/Rust protocol compatibility pass.
