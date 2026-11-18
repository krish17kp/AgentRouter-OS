# TASK-240 — Evaluation validate error parity

## Objective

Align the Rust evaluation CLI's invalid `validate-dataset` response with
Python's stable user-facing error prefix and exit code.

## Acceptance

- invalid dataset paths/names return exit 3;
- stderr begins with `Invalid dataset:`;
- the evaluation CLI, crate tests, Clippy, formatting, and diff checks pass.
