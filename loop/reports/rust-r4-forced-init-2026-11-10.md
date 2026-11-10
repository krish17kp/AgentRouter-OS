# Rust R4 forced initialization — 2026-11-10

## Scope

The Rust `init` probe now accepts `--force`. For ordinary files it backs up
existing config and registries to `.bak`, reseeds them, and emits the same
messages as Python. The default non-forced path remains idempotent.

## Security review and repair

An independent review reproduced two seed path escapes in the first
implementation: a linked `registry` directory redirected writes outside the
AgentRouter home, and a hard-linked `config.yaml` caused a forced write to
alter the outside file. The repair walks directories through no-follow
handles and replaces backup/seed directory entries relative to those handles.
Regression tests assert linked-parent refusal, unchanged outside files for
seed and backup hard links, and POSIX mode parity.

The same review reproduced an outside SQLite database modification through
a hard-linked `agentrouter.db`. The Rust probe now rejects linked database,
WAL, SHM, and journal paths before SQLite connects; tests cover database
symlinks and hard links. `agentrouter_storage::connect(home)` still opens the
database by a path, so a concurrent home/database path swap remains possible.
That is an R4 production blocker. Forced backup streams through a temporary
file, so it does not load the whole prior file into memory.

## Verification

- Focused Python/Rust init parity: 10 cases pass.
- Rust 1.75 workspace tests and current-toolchain Clippy with warnings denied:
  pass. Rustfmt passes.
- Full Python suite: 1,366 passed, 3 skipped.
- Previous head `6ee8d3e` passed all GitHub workflows; this slice awaits its
  own remote checks.

## Release status

This is a compatibility probe, not a production Rust CLI. Python remains
shipping. The canonical context-band gate remains 0.6667 < 0.90 and needs
the real-human annotation/adjudication round.
