# TASK-207 — Bounded orchestration runtime state

## Objective

Add a testable workflow lifecycle state machine behind the planning-only
orchestration boundary, covering dependency readiness, retry limits,
cancellation, and result aggregation without dispatching external work.

## Acceptance

- steps transition through pending/running/succeeded/failed/cancelled states;
- successful dependencies unlock downstream steps;
- failures retry only within each step's declared attempt budget;
- cancellation stops further starts and aggregates a cancelled result;
- all runtime results remain `execution_enabled: false`.
