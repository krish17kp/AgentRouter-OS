# TASK-212 Evidence

Date: 2026-11-17

## Implementation

- `agentrouter-storage::connect` now uses `SQLITE_OPEN_NOFOLLOW` for ordinary
  database paths, preventing a final-component symlink redirect.
- Linux `/proc/self/fd/<dirfd>` capability paths intentionally omit that flag
  because SQLite rejects the proc capability path itself; the pinned directory
  handle remains the parent-path protection used by safe initialization.
- Added a regression test proving a symlinked database leaf is rejected and its
  outside target remains unchanged.

## Verification

```text
cargo fmt --all -- --check  # passed
cargo test --locked -p agentrouter-storage -p agentrouter-cli
81 agentrouter-cli tests passed
15 agentrouter-storage tests passed
```

The pre-existing Linux parent-directory path-swap test also passes, including
database, WAL, and SHM creation beneath the renamed pinned directory.

The remaining SQLite leaf-swap/sidecar race is still tracked as an R4
limitation; this change narrows the ordinary symlink surface without claiming
complete handle-native SQLite initialization.
