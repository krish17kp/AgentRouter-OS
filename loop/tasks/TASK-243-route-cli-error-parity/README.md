# TASK-243 — Route CLI error parity

## Objective

Make malformed direct Rust route invocations, registry/config failures, and
runtime storage failures return Python-compatible CLI failures instead of an
uncaught panic exit.

## Evidence

- Unknown preferences, options, invalid controls, and malformed price caps now
  print an `Error:` diagnostic, emit no JSON, and exit 2.
- Missing positionals use exit 2; invalid registry/configuration uses exit 3;
  storage/learning failures use the runtime exit 1.
- The focused route compatibility suite passes 36 tests.
- The locked `agentrouter-cli` crate passes 89 tests and strict Clippy;
  formatting and diff checks pass.
