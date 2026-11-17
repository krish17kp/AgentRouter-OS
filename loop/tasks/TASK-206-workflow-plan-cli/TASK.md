# TASK-206 — Planning-only workflow CLI

## Objective

Expose the bounded orchestration planner through the unified Rust CLI without
introducing dispatch, tool grants, provider calls, or workspace mutation.

## Acceptance

- `agentrouter workflow plan` accepts a JSON step array or `{ "steps": [...] }`;
- explicit step/cost/tool policy flags are supported;
- valid workflows emit deterministic JSON/text plans with
  `execution_enabled: false`;
- malformed dependency declarations fail closed with a nonzero exit;
- locked CLI checks, orchestration tests, and a process smoke pass.
