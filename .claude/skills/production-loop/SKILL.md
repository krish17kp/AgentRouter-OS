---
name: production-loop
description: Run the AgentRouter OS per-task production loop end to end. Use when the user says "/production-loop", "run the loop", "next task", or asks to implement/fix/audit a backlog item. Creates or selects a task dir under loop/tasks/, drives INTAKE→DISCOVER→BASELINE→PLAN→TEST-FIRST→IMPLEMENT→VERIFY→AUDIT→REPAIR→REGRESSION→CUSTOMER REVIEW→RELEASE CHECK→RECORD, and stops only at a named terminal state.
---

# Production Loop

Governing spec: `command.md` (repo root). Control plane: `loop/`. Ponytail mode
is active — every change is the minimum that works after understanding the flow.

## Procedure

1. **Select task.** Read `loop/BACKLOG.yaml` and `LOOP_STATE.json`. Take the
   highest-priority `local_open` item unless the user named one. Never pick a
   `blocked_external` / `blocked_user` item to "implement".
2. **Create task dir.** Copy `loop/tasks/_TEMPLATE` to
   `loop/tasks/TASK-<n>-<slug>/`. Fill `task.yaml` (id, acceptance_criteria,
   verification_commands, affected_surfaces, risk).
3. **Discover** with the `repo-explorer` agent. Record sources in `research.md`.
4. **Baseline** (STEP 3): run focused tests + capture current CLI/API output +
   record git SHA into `loop/baselines/`. Never compare to an imagined baseline.
5. **Plan** with `product-architect` for non-trivial work → `plan.md` + `risk.md`.
6. **Test-first contract** → `test-plan.md` (positive/negative/boundary/security).
7. **Implement** with `implementation-engineer` (worktree isolation, assigned
   files only) → `implementation-log.md`.
8. **Focused verify**: smallest checks first (targeted pytest, ruff, bandit).
9. **Independent audit**: `verification-engineer` + `security-reviewer-arros`
   (sensitive) + `customer-advocate` (customer-facing) + `product-architect`
   (structural). None may be the implementer.
10. **Repair loop**: reproduce → classify → root-cause fix → regression test →
    re-verify. Max 4 iterations per symptom, then escalate (redesign or blocker).
11. **Maintainability + full regression**: `python -m pytest -q` must stay green.
12. **Customer review** against `loop/PRODUCT_SCENARIOS.yaml`.
13. **Release check**: `release-auditor` traces requirement→impl→test→output→docs.
14. **Record**: update task `evidence.json`, `LOOP_STATE.json`, `LOOP_LOG.md`,
    `QUALITY_DASHBOARD.md`, `RELEASE_READINESS.md`. Select next task.

## Autonomy
Routine, reversible, local, no-cost, credential-free tasks never need owner confirmation.
Auto-continue to the next task whenever BOTH: (a) another locally actionable task exists, and
(b) it needs no money, credentials, deployment, destructive op, merge, release, or public push.
Ask the owner ONLY for: pushing the RC branch while a mandatory gate fails; merge to main;
publication/deployment/paid inference/credentials; destructive changes. Do not stop after one task.

## Stop conditions
PRODUCTION_READY / PUBLIC_BETA_READY / BLOCKED_EXTERNAL / BLOCKED_USER / UNSAFE /
ENVIRONMENT_FAILURE / CONTEXT_HANDOFF. Never claim done on one green run.

## Git
Never `git add`/`commit`/`push`/`tag`/PR. Read-only git only.
