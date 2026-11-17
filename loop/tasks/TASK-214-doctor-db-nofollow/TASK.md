# TASK-214 — Doctor database no-follow hardening

## Objective

Keep the read-only Rust diagnostics path from following a symlinked decision
database outside the selected AgentRouter home.

## Acceptance

- `agentrouter doctor` opens an existing database with SQLite no-follow flags;
- a symlinked `agentrouter.db` produces a safe unreadable-database finding;
- the outside target is not modified or treated as the home database;
- focused diagnostics tests, formatting, and strict Clippy pass;
- the hardening is documented without claiming complete database handle parity.
