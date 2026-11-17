# TASK-209 Evidence

Date: 2026-11-17

## Verification

```text
AGENTROUTER_PARITY_SERVER=rust AGENTROUTER_REQUIRE_LIVE=1 npm test --prefix sdk/typescript
18 passed, 0 failed, 0 skipped
```

The parity helper now uses `target/debug/init_cli` for Rust homes, so the
Rust live-server suite no longer depends on Python/Typer initialization.
