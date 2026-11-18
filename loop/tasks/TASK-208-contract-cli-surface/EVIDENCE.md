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
- Candidate diffs now reject non-OpenAPI documents and unusable local `$ref`
  targets before the surface analyzer runs.

## Verification

```text
1 passed, 17 deselected in 1.22s
cargo check --locked -p agentrouter-cli --bin agentrouter  # passed
```

The command intentionally does not claim a live FastAPI schema check; the
Python contract gate remains authoritative until the full live-schema port is
complete.
