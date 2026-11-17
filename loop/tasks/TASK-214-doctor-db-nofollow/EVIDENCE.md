# TASK-214 Evidence

Date: 2026-11-18

## Implementation

- Added `SQLITE_OPEN_NOFOLLOW` to the Rust doctor's read-only database open.
- Added a Unix regression with a symlinked `agentrouter.db`; the check returns
  `data.database=FAIL` and leaves the outside target unchanged.

## Verification

```text
cargo fmt --all -- --check  # passed
cargo test --locked -p agentrouter-cli diagnostics::tests  # 3 passed
```

The normal storage open and Linux capability-pinned initialization remain
covered separately by TASK-212. Complete handle-native SQLite initialization
and pathname-based sidecar race closure remain documented R4 limitations.
