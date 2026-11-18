# TASK-209 — TypeScript SDK live Rust parity

## Objective

Make the TypeScript SDK's Rust live-server parity mode independent of the
Python package and require the full loopback suite to run instead of silently
skipping when Python extras are absent.

## Acceptance

- Rust parity homes are initialized with the Rust `init_cli` binary;
- `AGENTROUTER_REQUIRE_LIVE=1 AGENTROUTER_PARITY_SERVER=rust npm test --prefix sdk/typescript`
  completes with zero skips;
- the Python parity path remains unchanged;
- no credentials or external network calls are introduced.
