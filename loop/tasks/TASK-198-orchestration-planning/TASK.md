# TASK-198 — Bounded orchestration planning

## Objective

Add a Rust-native dependency-graph planner for future multi-agent workflows
without dispatch, tool grants, workspace mutation, or execution.

## Acceptance

- reject empty, duplicate, unknown, cyclic, and invalid-attempt workflows;
- enforce step and estimated-cost budgets before planning;
- produce deterministic dependency levels;
- reject conflicting side-effect keys in one parallel level;
- keep `execution_enabled: false` in the returned plan.
