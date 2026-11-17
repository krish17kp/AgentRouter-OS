# TASK-185 — Plugin doctor symlink-root diagnosis

## Objective

Ensure a symlinked or reparse-point plugin root is reported as an actionable
blocked destination, not as an internal diagnostic bug. The doctor must remain
safe and useful when a host uses a linked configuration directory.

## Acceptance

- linked plugin roots are detected before journal/state probing;
- the finding is `check: destination`, `status: blocked`, with a path-specific
  remedy;
- no linked target is followed or modified;
- focused tests, strict Clippy, formatting, and diff checks pass.
