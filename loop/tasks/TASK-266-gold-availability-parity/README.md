# TASK-266 — gold adapter availability parity

## Outcome

The Rust registry facade now reports the committed `agentrouter-gold`
benchmark as `ready`, matching Python `AgentRouterGoldAdapter.availability()`.
The facade still reports real mode as explicitly unavailable because the gold
set is project-local rather than an external loader.

## Evidence

- `cargo test -p agentrouter-evaluation --lib`: 16 passed.
- Focused Python/Rust evaluation and gold-adapter selection: 13 passed.
- The new Rust regression loads all 165 committed gold cases and verifies the
  `ready` availability and description fields.

## Scope boundary

This closes one adapter-facade contract mismatch only. External benchmark
loaders, frozen human evaluation, hosted approval, credentials, and deployment
remain open release gates.
