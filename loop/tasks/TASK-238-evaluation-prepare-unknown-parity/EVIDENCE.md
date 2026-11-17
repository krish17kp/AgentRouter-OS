# TASK-238 Evidence

Date: 2026-11-18

## Verification

Rust `agentrouter-evaluate prepare --dataset does-not-exist` now matches
Python's unavailable-adapter behavior instead of failing with an unknown
registry error.

```text
tests/test_rust_evaluation_cli_compat.py   22 passed
agentrouter-evaluation Rust tests          14 passed
full locked Rust workspace tests            passed
strict workspace Clippy / rustfmt / diff    passed
Ruff check / format check                  passed
```
