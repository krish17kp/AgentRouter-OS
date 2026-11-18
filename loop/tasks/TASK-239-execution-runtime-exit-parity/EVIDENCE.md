# TASK-239 Evidence

Date: 2026-11-18

## Verification

The Rust execution path now returns Python-compatible runtime exit code 1 for
child-process launch failures and OpenAI/host transport failures. A unified CLI
regression exercises a missing configured command and verifies that no usage or
registry code is returned.

```text
tests/test_rust_unified_cli_compat.py   20 passed
agentrouter-cli Rust tests              89 passed
strict Clippy / rustfmt / diff checks   passed
```
