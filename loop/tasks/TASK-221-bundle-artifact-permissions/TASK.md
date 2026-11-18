# TASK-221 — Private Rust diagnostic-bundle artifacts

## Objective

Match the Python diagnostic bundle's Unix privacy boundary for every generated
artifact, while retaining capability-bounded no-follow creation.

## Acceptance

- Rust bundle artifacts are created with mode `0600` on Unix;
- the mode is set on the opened file handle, not through a path-based race;
- existing redaction, size limits, symlink refusal, and snapshot behavior remain
  unchanged;
- focused Rust and Python/Rust bundle checks pass with strict Clippy.
