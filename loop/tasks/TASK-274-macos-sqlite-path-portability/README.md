# TASK-274 — macOS SQLite path portability

## Outcome

Rust storage now resolves existing parent path components before opening the
SQLite database with `SQLITE_OPEN_NOFOLLOW`. This preserves final-database
symlink protection while allowing macOS temporary directories, whose `/var`
component is a symlink to `/private/var`, to open successfully.

The Linux `/proc/self/fd/<dirfd>` capability path remains uncanonicalized so
directory-handle pinning is preserved.

## Evidence

- `cargo test --workspace --locked`: pass.
- `cargo test -p agentrouter-storage --locked`: 15 tests pass.
- `.venv/bin/pytest -q tests/test_store_rust_compat.py tests/test_evaluation_metrics_rust_compat.py`: 69 tests pass.
- The hosted macOS failures were reproduced in logs as SQLite `CANTOPEN` on
  `/var/folders/...`; the fix targets that platform-specific path behavior.

## Scope boundary

This fixes hosted cross-platform storage compatibility. It does not change the
honest release gate, live-smoke credentials, human evaluation, approval, or
deployment requirements.
