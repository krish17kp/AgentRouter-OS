# TASK-251 — Public stored-prompt newline parity

## Objective

Keep the direct Rust decision probe's historical output contract while making
the unified public `prompt generate --from` output identical to Python.

## Evidence

- Unified stored-prompt output now includes Python's final newline; the direct
  `decision_cli` probe remains newline-free for its existing differential.
- A process-level Python/Rust comparison covers the public stored-prompt path.
- The focused decision/unified CLI selection passes 45 tests; strict Clippy,
  formatting, and diff checks pass.
