# TASK-173 — Diagnostic bundle safety audit

Audit the Rust diagnostic bundle against Python's allowlisted, secret-safe
bundle writer. The Rust implementation already redacts JSON/text, bounds
artifacts, refuses existing destinations, snapshots SQLite through the storage
layer, and keeps database inclusion opt-in.

## Increment

- Replace path-based final artifact and database-snapshot creation with a pinned
  capability directory and `create_new`, preventing concurrent symlink/reparse
  redirection on the final component.
- Add a regression proving a symlinked bundle artifact cannot overwrite a file
  outside the bundle.
- Keep the row Partial: complete Python/Rust environment metadata and all
  Windows-specific bundle edge cases still need differential evidence.

## Evidence

Rust bundle tests, strict Clippy, and the focused Python bundle/diagnostics suite
pass after the capability-directory write change.
