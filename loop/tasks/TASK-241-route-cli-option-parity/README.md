# TASK-241 — Route CLI classifier-option parity

## Objective

Align the Rust direct `route` command with Python's classifier override,
preference, logging, and compatibility flags.

## Acceptance

- classifier overrides reach Rust classification;
- preference flags match Python and reject conflicts;
- `--no-log`, `--allow-preview`, and `--include-unavailable` preserve the
  Python-compatible command surface;
- focused compatibility tests, the locked Rust workspace, strict Clippy,
  formatting, and diff checks pass.
