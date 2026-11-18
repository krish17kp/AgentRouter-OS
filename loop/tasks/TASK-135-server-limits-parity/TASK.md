# TASK-135 — Close server limits behavioral parity

## Objective

Complete the Python/Rust contract evidence for `agentrouter/server/limits.py`
and `agentrouter-limits`, including the language-native single-flight APIs.

## Scope

- Compare Python asyncio single-flight and Rust keyed computation outcomes.
- Verify successful responses replay once per key, while exceptions and non-2xx
  outcomes are recomputed.
- Verify separate keys proceed independently and response fields remain intact.
- Retain existing differential coverage for rate limits, environment settings,
  TTL boundaries, and existing Rust/Python capacity tests.
- Mark module parity only after focused and workspace tests pass.
