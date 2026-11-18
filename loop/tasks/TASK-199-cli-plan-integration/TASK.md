# TASK-199 — Read-only CLI planning integration

## Objective

Expose the fail-closed execution planner through the unified Rust CLI without
starting a process, calling a provider, or reading a credential.

## Acceptance

- `agentrouter plan <decision-id>` loads a persisted decision and registry;
- text and JSON output expose the plan and `execution_enabled: false`;
- missing decisions and blocked routes return safe non-zero results;
- explicit policy flags only affect planning and never enable execution.
