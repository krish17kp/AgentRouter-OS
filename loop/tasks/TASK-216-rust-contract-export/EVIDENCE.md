# TASK-216 Evidence

Date: 2026-11-18

## Implementation

- Added `agentrouter contract export` to the unified Rust CLI.
- Added optional `--source PATH`, `--generated-at RFC3339`, and `--json` output.
- Existing baselines are loaded and checked for breaking surface changes before
  any replacement; missing or unreadable baselines remain fail-closed.
- The default source is the committed Rust OpenAPI artifact, so the command is
  deterministic and does not claim live FastAPI schema parity.

## Verification

```text
cargo fmt --all
cargo check -p agentrouter-cli --bin agentrouter  # passed
cargo build -p agentrouter-cli --bin agentrouter   # passed
temporary-root contract export with --source/--generated-at  # passed
```

The complete live-schema exporter and compatibility classifier remain Python-
owned; this closes the public Rust export wiring without overstating parity.
