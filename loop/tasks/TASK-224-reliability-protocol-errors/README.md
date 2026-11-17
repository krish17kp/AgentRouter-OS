# TASK-224 — Reliability protocol-error parity

## Objective

Match Python/HTTPX transport classification for truncated HTTP response bodies
without collapsing ordinary read failures into protocol errors.

## Acceptance

- truncated declared-length responses report `RemoteProtocolError`;
- timeout responses remain `ReadTimeout`;
- other read failures remain `ReadError`;
- focused Python/Rust compatibility and strict Rust checks pass.
