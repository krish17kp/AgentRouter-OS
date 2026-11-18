# TASK-203 — Shared execution-planner preflight

## Objective

Make the Rust fail-closed execution planner the shared authorization/readiness
preflight for guarded CLI execution without allowing the planner to execute a
provider, process, or command.

## Acceptance

- API and CLI adapter readiness are explicit planner policy inputs;
- guarded execution invokes the planner after persisted safety and route
  integrity checks;
- dry-run remains read-only and can preview unavailable routes;
- planner tests, workspace checks, strict Clippy, and formatting pass;
- documentation records that adapters remain separately gated.
