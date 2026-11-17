# TASK-215 Evidence

Date: 2026-11-18

## Implementation

- Added `SQLITE_OPEN_NOFOLLOW` to Rust bundle `decision_shape` database reads.
- Added a Unix regression proving a symlinked `agentrouter.db` is rejected and
  the outside target remains unchanged.

## Verification

```text
cargo fmt --all -- --check  # passed
cargo test --locked -p agentrouter-cli bundle::tests  # 7 passed
```

The diagnostics check and normal storage open are hardened separately by
TASK-214 and TASK-212. Full handle-native SQLite and pathname-sidecar parity
remain open R4 limitations.
