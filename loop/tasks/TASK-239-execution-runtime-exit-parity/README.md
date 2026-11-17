# TASK-239 — Execution runtime exit-code parity

## Objective

Align the Rust guarded execution command with the Python CLI contract for
runtime failures. Missing child commands and failed OpenAI/host transport
operations must return `EXIT_RUNTIME` (1), not the registry/usage code 3.

## Acceptance

- a missing configured execution command returns exit 1;
- the error remains bounded and identifies the failed command;
- the unified CLI process regression passes;
- Rust CLI tests, Clippy, formatting, and diff checks pass.
