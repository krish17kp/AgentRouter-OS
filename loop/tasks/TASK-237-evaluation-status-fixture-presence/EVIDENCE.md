# TASK-237 Evidence

Date: 2026-11-18

## Verification

Rust `agentrouter-evaluate status` now checks the registered fixture path
directly instead of inferring availability from the loaded case count. A
relocated project containing an empty `massive_sample.jsonl` reports
`fixture: true`, matching Python's path-based `DatasetAdapter.availability()`
contract.

```text
tests/test_rust_evaluation_cli_compat.py   22 passed
agentrouter-evaluation Rust tests          14 passed
strict Clippy / rustfmt / diff checks      passed
full locked Rust workspace tests            passed
```
