# TASK-225 — SDK protocol-error parity

## Objective

Align the native Rust SDK's truncated-response classification with Python's
HTTPX client while preserving distinct timeout and generic read errors.

## Acceptance

- truncated declared-length responses report `RemoteProtocolError`;
- timeout and generic read-error categories remain distinct;
- native Rust and Python SDK compatibility suites pass.
