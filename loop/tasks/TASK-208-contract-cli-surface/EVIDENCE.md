# TASK-208 Evidence

Date: 2026-11-17

## Implementation

- Added `agentrouter contract check [--json]` to validate the committed Rust
  OpenAPI baseline and report `live_schema_check: false` explicitly.
- Added `agentrouter contract diff PATH|- [--json]` using the existing bounded
  Rust surface analyzer. Additive changes remain compatible; breaking changes
  return exit code 1.
- Added process coverage for baseline validation, additive diffs, and breaking
  diffs in `tests/test_rust_unified_cli_compat.py`.

## Verification

```text
2 passed, 16 deselected in 2.21s
cargo check --locked -p agentrouter-cli --bin agentrouter  # passed
```

The command intentionally does not claim a live FastAPI schema check; the
Python contract gate remains authoritative until the full live-schema port is
complete.
