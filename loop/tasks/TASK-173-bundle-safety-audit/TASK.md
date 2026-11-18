# TASK-173 — Diagnostic bundle safety audit

Audit the Rust diagnostic bundle against Python's allowlisted, secret-safe
bundle writer. The Rust implementation already redacts JSON/text, bounds
artifacts, refuses existing destinations, snapshots SQLite through the storage
layer, and keeps database inclusion opt-in.

## Increment

- Replace path-based bundle-parent, final artifact, and database-snapshot
  creation with no-follow component walking, a pinned capability directory, and
  `create_new`, preventing concurrent symlink/reparse redirection on any
  destination component while preserving nested-parent creation.
- Serialize the committed SQLite main database in memory, create the final
  snapshot with `create_new`, and write/sync through that one opened handle;
  this avoids reopening a pathname after safe creation and closes the
  concurrent symlink/hard-link replacement race.
- Add regressions proving symlinked bundle artifacts, hard-linked snapshot
  destinations, and a swapped bundle directory cannot overwrite files outside
  the pinned bundle.
- Keep the row Partial: complete Python/Rust environment metadata and all
  Windows-specific bundle edge cases still need differential evidence.

## Evidence

Rust bundle/storage tests, strict Clippy, and the focused Python
bundle/diagnostics suite pass after the capability-directory and one-shot
serialized snapshot changes.
