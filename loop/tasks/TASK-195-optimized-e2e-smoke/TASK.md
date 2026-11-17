# TASK-195 — Optimized binary end-to-end smoke

## Objective

Exercise the optimized release binary from a fresh isolated home, including
initialization, routing, diagnostics, and MCP stdio negotiation.

## Acceptance

- fresh-home `init`, `route --json`, and `doctor --json` succeed;
- the binary reports the release-candidate version;
- MCP initialize and tools/list return the expected protocol and five safe tools;
- no credentials, publication, or deployment are used.
