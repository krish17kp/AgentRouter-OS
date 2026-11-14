# TASK-113 — Rust plugin replacement and transaction recovery

## Objective

Complete the Rust plugin install lifecycle for forced replacement of unmanaged
files and interrupted transaction recovery. Preserve Python-compatible
ownership and journal formats while refusing ambiguous or user-edited data.

## Contract cases

- Refuse symlinks, reparse points, hard-linked source files, unsafe paths, and
  pre-existing backup collisions before replacing a destination.
- Write and validate the private journal phases `prepared`, `backing_up`
  (intent), `backed_up` (backup committed), and `replaced`; use exclusive backup
  creation and record payload digest, file identity, and permission mode.
- Create the replacement at a private staging path and persist its identity
  before moving the original destination. Recovery may discard only an
  identity-verified replacement stage; pre-identity or mismatched files remain
  untouched.
- Recover only when the journal, destination, backup, ownership state, identity,
  digest, and mode prove one safe outcome. Preserve all paths and the journal
  when evidence is ambiguous or a concurrent edit appears.
- A crash after replacement but before state persistence must reconstruct the
  same Python-compatible ownership record; a crash after state persistence but
  before journal deletion must only clean up the verified journal.
- Interoperate both ways: Python-created transaction records can be recovered
  by Rust, and Rust-created state/backups can be recovered or uninstalled by
  Python.
- Keep managed upgrades as a separately tracked lifecycle case unless the
  transaction contract can cover them without changing Python semantics.

## Verification

Add regression tests for every transaction phase and fault boundary, including
same-inode backup collisions, byte-identical concurrent destinations, crashes
before and after replacement-identity commit, rollback cleanup interruption,
corrupt journals, interrupted backup and state writes, and ambiguous recovery.
Run the complete plugin suite, Rust workspace and strict Clippy, full Python
regression with coverage, Ruff, formatting, dependency audits, and hosted
Linux/Windows/macOS Rust plus Python/Rust compatibility checks.

Do not weaken the frozen context-band evaluation or mark the release ready
without the independent human annotation round.
