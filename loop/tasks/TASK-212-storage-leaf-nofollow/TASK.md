# TASK-212 — SQLite database-leaf no-follow hardening

## Objective

Close the ordinary-path final-component symlink gap in the Rust SQLite storage
open while preserving the Linux capability-pinned home path used by the safe
`init` flow.

## Acceptance

- Rust storage opens ordinary database paths with SQLite's no-follow flag;
- a symlinked `agentrouter.db` is rejected without modifying its target;
- capability-pinned Linux initialization continues to create the database and
  WAL sidecars in the pinned directory after a parent-path swap;
- storage and CLI focused tests, formatting, and strict Clippy remain green;
- the remaining leaf-swap limitation for SQLite's pathname-based sidecars is
  documented honestly and is not presented as complete production parity.
