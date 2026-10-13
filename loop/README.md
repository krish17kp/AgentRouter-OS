# Loop Control Plane

This directory is the persistent control plane for the AgentRouter OS production
loop (see `command.md` at repo root). It exists so any fresh Claude session can
resume work without relying on conversation memory.

## Layout

| Path | Purpose |
|------|---------|
| `BACKLOG.yaml` | Prioritized production backlog (source of truth for "next task"). |
| `QUALITY_GATES.yaml` | Machine-readable release gates + thresholds. |
| `PRODUCT_SCENARIOS.yaml` | Customer scenarios the product must satisfy. |
| `PLUGIN_SKILL_INVENTORY.yaml` | Inventory of available plugins/skills/agents/hooks/MCP. |
| `PLUGIN_SKILL_DECISIONS.md` | Use / disable / conditional decisions + rationale. |
| `tasks/TASK-<n>-<slug>/` | One directory per task (see `_TEMPLATE/`). |
| `reports/` | Audit reports, skill evals, benchmark output. |
| `baselines/` | Captured baselines (tests, eval, wheel) before behavior changes. |
| `handoffs/` | Paste-ready continuation prompts for CONTEXT_HANDOFF. |

## Root-level state (maintained alongside this dir)

`LOOP_STATE.json`, `LOOP_LOG.md`, `PRODUCT_MASTER_PLAN.md`, `PRODUCT_ACCEPTANCE.md`,
`ARCHITECTURE_DECISIONS.md`, `KNOWN_LIMITATIONS.md`, `RELEASE_READINESS.md`,
`QUALITY_DASHBOARD.md`, `PRODUCTION_READINESS.md`.

## Per-task lifecycle

INTAKE → DISCOVER → BASELINE → PLAN → TEST-FIRST → IMPLEMENT → VERIFY →
AUDIT → REPAIR → MAINTAINABILITY → REGRESSION → CUSTOMER REVIEW →
RELEASE CHECK → RECORD → NEXT.

Start a task with the `/production-loop <task>` skill, or copy `tasks/_TEMPLATE`
to a new task dir and fill `task.yaml`.
