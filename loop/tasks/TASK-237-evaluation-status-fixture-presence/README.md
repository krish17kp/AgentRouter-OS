# TASK-237 — Evaluation status fixture presence parity

## Objective

Align Rust evaluation `status` with Python's adapter contract by reporting a
fixture as available when its file exists, even when the fixture contains zero
records.

## Acceptance

- a relocated empty fixture is reported as `fixture: true`;
- the evaluation CLI differential suite remains green;
- Rust evaluation tests, strict Clippy, formatting, and diff checks pass.
