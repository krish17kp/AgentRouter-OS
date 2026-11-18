# TASK-191 — MCP malformed-input hardening

## Objective

Close the remaining local MCP lifecycle/error coverage gap with explicit
fail-closed tests for malformed JSON-RPC requests and invalid tool arguments.

## Acceptance

- malformed requests return stable JSON-RPC errors;
- missing and invalid tool arguments return safe tool errors without panics;
- the read-only five-tool surface remains unchanged;
- focused and full Rust checks pass;
- no execution or external credential behavior is introduced.
