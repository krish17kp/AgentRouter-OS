# TASK-112 — Python-compatible Rust plugin uninstall

## Objective

Implement `agentrouter plugin uninstall NAME` in Rust without weakening the
Python plugin manager's ownership, backup, link, or user-edit safeguards.

## Contract cases

- Remove a file only when its recorded installed digest and filesystem identity
  still match; preserve unmanaged, pre-existing, edited, linked, and hard-linked
  files.
- Restore only a backup whose digest, identity, and permission mode match the
  ownership record. Handle a missing destination and an already completed
  backup restoration without overwriting a concurrent destination.
- Clear ownership records after completed removal, retain ambiguous records for
  retry, and remove only identity-matched empty cleanup/state directories.
- Handle older ownership records containing paths no longer present in the
  current plugin manifest.
- Keep Rust-produced output and JSON ownership state interoperable with Python.

## Verification

Run the focused Python/Rust plugin compatibility suite, Python plugin safety
and adversarial tests, full Rust workspace tests and strict Clippy, the full
Python regression/coverage run, formatting, Ruff, and hosted Linux/Windows/macOS
CI. Keep the context-band release gate and human-annotation requirements intact.

## Remaining scope

Rust force replacement, managed upgrades, and interrupted transaction recovery
remain separate lifecycle tasks. They must not be claimed as migrated here.
