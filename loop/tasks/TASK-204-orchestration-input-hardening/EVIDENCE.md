# TASK-204 evidence

Date: 2026-11-17

`agentrouter-orchestration` now rejects duplicate dependencies and empty
side-effect keys before dependency-level scheduling. The checks complement the
existing cycle, step/cost budget, retry, tool allowlist, idempotency, and
parallel side-effect conflict guards.

```console
cargo fmt --all
cargo test --locked -p agentrouter-orchestration
# 5 passed
cargo clippy --locked -p agentrouter-orchestration --all-targets -- -D warnings
# pass
```

The crate remains planning-only: `execution_enabled` is false and no agent,
tool, workspace, or provider is dispatched.
