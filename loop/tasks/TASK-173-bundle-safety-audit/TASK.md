# TASK-173 — Diagnostic bundle safety audit

Audit the Rust diagnostic bundle against Python's allowlisted, secret-safe
bundle writer. The Rust implementation already redacts JSON/text, bounds
artifacts, refuses existing destinations, snapshots SQLite through the storage
layer, and keeps database inclusion opt-in.

## Increment

- Replace path-based final artifact and database-snapshot creation with a pinned
  capability directory and `create_new`, preventing concurrent symlink/reparse
  redirection on the final component.
- Open the SQLite snapshot target with `SQLITE_OPEN_NOFOLLOW` as well; the
  pathname is no longer reopened without a no-follow policy after safe creation.
- Add regressions proving symlinked bundle artifacts and snapshot destinations
  cannot overwrite files outside the bundle.
- Keep the row Partial: complete Python/Rust environment metadata and all
  Windows-specific bundle edge cases still need differential evidence.

## Evidence

Rust bundle/storage tests, strict Clippy, and the focused Python
bundle/diagnostics suite pass after the capability-directory and SQLite
no-follow changes.
