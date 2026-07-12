# AgentRouter OS — Milestones

> **Purpose:** Turn each roadmap phase into an executable milestone with goals,
> tasks, outputs, a validation checklist, completion criteria, dependencies, and
> risks. Milestones map **1:1** to [ROADMAP.md](ROADMAP.md) phases. Tier labels
> match the shared set: **MVP → Capstone demo → Advanced → Production-future.**

---

## M1 — MVP CLI  · tier: **MVP**  · depends on: none

**Goal:** Classify → recommend + fallback → prompt + checklist → log, over
static registries.

**Tasks**
- Scaffold Typer app + `init`; establish `~/.agentrouter/` layout.
- Pydantic models for `ModelEntry` (per [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md)) and `Classification`.
- ModelRegistry + ProviderRegistry loaders with load-time validation.
- Rule-based TaskClassifier (7 dimensions).
- RoutingEngine: eligibility filters, scoring formula, fallback selection ([ROUTING_RULES.md](ROUTING_RULES.md)).
- SafetyEngine: risk → checklist + gates.
- PromptGenerator.
- SQLite DecisionLog; `route`, `explain` (basic), `registry list`, `prompt generate`.
- Seed registry with entries for all six provider types.

**Outputs:** runnable `agentrouter` CLI; seed registries; SQLite schema.

**Validation checklist** — ✅ complete (covered by `tests/test_mvp.py`)
- [x] `init` creates config + registries + DB.
- [x] `route` returns ≥1 recommendation + ≤1 fallback for the three sample tasks (script / auth refactor / long summary).
- [x] Malformed YAML entry → exit code 3 naming the field (FR-2).
- [x] 300k-token task excludes sub-300k-context models (FR-5).
- [x] `risk=high` → `human-approval-required` + ≥3 checklist items, no auto-execute flag (FR-6/8).
- [x] `explain <id>` reproduces the printed decision (FR-11).
- [x] No current model name appears in engine code (NFR-2).

**Completion criteria:** all MVP acceptance criteria in [PRD.md](PRD.md) pass.

**Risks:** classifier heuristics too crude → allow manual `--risk/--tool/--context-tokens` overrides.

---

## M2 — Live catalog + polished demo  · tier: **Capstone demo**  · depends on: M1

**Goal:** `providers refresh` syncs live model lists; rich `explain`; demo-ready.

**Tasks**
- Implement `refresh_models` for the API/CLI adapters (read-only auth).
- `providers refresh` command (+ `--provider`, `--dry-run`).
- Rich `explain` score table + weight-shift display.
- `--json` output across commands; output formatting polish.
- Expand seed registry to realistic size.

**Outputs:** live-refreshable registry; demo script.

**Validation checklist** — ✅ complete (`tests/test_refresh.py` + live smoke)
- [x] `providers refresh` updates the registry with no code change (FR-12).
- [x] Refresh is idempotent (re-run → no duplicates).
- [x] `explain` shows full eligibility + score breakdown.
- [x] Demo routes ≥4 task types across ≥3 real providers.

**Completion criteria:** scripted multi-provider demo runs clean end-to-end.

**Risks:** provider API/auth changes → isolated in adapters; catalog-only fallback if auth absent.

---

## M3 — Adapter expansion & hardening  · tier: **Capstone demo → Advanced**  · depends on: M2

**Goal:** Broad, robust provider coverage; trivial to add new providers.

**Tasks**
- Generic CLI-agent adapter (config-driven).
- Staleness warnings from `last_updated`; robust `map_capabilities`.
- Adapter test harness with mocked provider responses.

**Outputs:** hardened adapters; test harness.

**Validation checklist** — ✅ complete (`tests/test_refresh.py`, `tests/test_registry_hygiene.py`)
- [x] A brand-new provider added via new adapter + YAML only, routable end-to-end (OpenAI adapter: `fetch_openai_models` + registry entries, zero engine change).
- [x] Stale entries surface a warning (`last_updated` > 90 days).
- [x] Adapter tests pass against mocked responses (no network, no keys in pytest).

**Completion criteria:** "new provider = new adapter + YAML, zero engine change" demonstrated.
*Note: the config-driven generic CLI-agent adapter was skipped (YAGNI) — the
dispatch-table pattern in `refresh.py` makes each new adapter one function + one
table row; add the generic adapter when a third refreshable provider shows real
config overlap. Curated `ability_overrides.yaml` shipped here too.*

**Risks:** inconsistent upstream metadata → conservative defaults + validation.

---

## M4 — Feedback learning loop  · tier: **Advanced**  · depends on: M1 (log), M2

**Goal:** Recommendations improve from logged outcomes.

**Tasks**
- `feedback` command + FeedbackStore schema.
- Bounded weight-adaptation from ratings/accept-override signals.
- Acceptance-rate + drift reporting.

**Outputs:** feedback pipeline; adaptive weights.

**Validation checklist** — ✅ complete (`tests/test_learning.py`)
- [x] `feedback` persists and links to a `decision_id`.
- [x] Repeated negative feedback shifts weights within bounds (step 0.01, cap +0.10, `w_cost` floor 0.05, min 3 ratings).
- [x] Weight changes are logged (in `weight_shifts`) and reversible (recomputed from the feedback table; delete rows or `learning: false` reverts).

**Completion criteria:** feedback measurably changes later recommendations in a controlled test — verified by `test_feedback_changes_later_recommendation_weights`.

**Risks:** overfitting to sparse feedback → clamp nudge size; require minimum sample.

---

## M5 — Web dashboard  · tier: **Advanced**  · depends on: M1 (log), M4 (optional)

**Goal:** Read-only visibility over decisions and trends.

**Tasks**
- FastAPI read-only endpoints over DecisionLog/FeedbackStore.
- Dashboard views: history, acceptance rate, cost-tier distribution.

**Outputs:** dashboard app.

**Validation checklist** — ✅ complete (`tests/test_dashboard.py`)
- [x] Dashboard renders live from local DB (recomputed per request).
- [x] No write path from dashboard into routing (GET-only handler, no forms/scripts).

**Completion criteria:** dashboard usable against a populated DB.
*Note: built on stdlib `http.server` instead of FastAPI — zero new dependencies
for a strictly read-only local page; swap to FastAPI if it ever needs auth or an API.*

**Risks:** scope creep into a full web app → keep strictly read-only in this tier.

---

## M6 — Execution automation  · tier: **Production-future**  · depends on: M2, M3

**Goal:** Optionally run the recommended tool, with hard safety gating.

**Tasks**
- Implement real `execute` for the strongest execution-capable adapter first.
- Auth/secret management.
- Enforce: `risk=high` never auto-executes without human approval (NFR-8).

**Outputs:** execution path; secret handling.

**Validation checklist** — ✅ complete (`tests/test_execute.py`)
- [x] A `risk=low` task executes end-to-end from the CLI (`execute <id> --yes`, provider opt-in required).
- [x] A `risk=high` task is provably blocked from auto-execution (blocked even with every provider enabled; tested).
- [x] No secrets logged or committed (AgentRouter stores no execution secrets — provider CLIs carry their own auth; refresh keys are env-only, header-only).

**Completion criteria:** low-risk execution works; high-risk gating verified.

**Risks:** security exposure → dedicated secret store; execution behind explicit opt-in flag.

---

## M7 — Teams & telemetry  · tier: **Production-future**  · depends on: M5, M6

**Goal:** Multi-user, governed deployment.

**Tasks**
- Shared registry + team config + policy controls.
- Usage telemetry + aggregate cost reporting.
- Hosting beyond single-user local.

**Outputs:** team mode; telemetry.

**Validation checklist** — ✅ complete (`tests/test_stats.py`)
- [x] Team shares one registry + policy (shared `AGENTROUTER_HOME` directory).
- [x] Per-user history + aggregate cost reporting available — every decision
      records a user (`AGENTROUTER_USER` env, falling back to the OS
      username); `stats` reports `by_user`; the dashboard shows a per-user
      table and a user column; `explain` returns the user. Pre-M7 databases
      migrate in place (rows show as `unknown`).
- [x] Policy controls enforce routing/safety rules org-wide (`policy.max_pricing_tier` in shared config; high-risk execution gate is unconditional).

**Completion criteria:** a team operates from shared config with per-user history and cost visibility — **met** for the local-first scope: shared config + policy + per-user history + aggregate stats. *Hosting beyond a shared directory (multi-tenant service, auth) remains explicitly out of scope for a local CLI; revisit only if a service surface appears.*

**Risks:** multi-tenant complexity → phase carefully after single-user is solid.

---

## M8 — Agent skill integration  · tier: **Production-future**  · depends on: M1–M4

**Goal:** AgentRouter usable *inside* any agent CLI/IDE (Claude Code, Codex,
Antigravity, Cursor, …) as a skill/instruction protocol, with auto/manual
modes and per-subtask routing to save tokens.

**Tasks**
- Portable skill: `integrations/claude-code/agentrouter/SKILL.md` (modes,
  decomposition protocol, tier→host-model mapping, safety gates).
- Host-agnostic protocol snippet: `integrations/AGENTS.md` (Codex,
  Antigravity, Cursor, generic system prompts).
- `pricing_tier` exposed in `route --json` score rows so hosts map
  recommendations onto their own model lineup without a second call.
- Install docs per host (`integrations/README.md`).

**Design:** the *host agent* (an LLM) decomposes tasks into subtasks;
AgentRouter (rule-based, auditable) routes each subtask to a pricing tier; the
host maps tiers onto whatever models it actually has (haiku/sonnet/opus,
mini/full, flash/pro/ultra). Auto mode executes via subagents where supported;
`risk=high` / `auto_execute_allowed=false` is never auto-executed in any mode.

**Validation checklist** — ✅ complete
- [x] `route --json` carries `pricing_tier` on recommendation/fallback/scores
      (`tests/test_stats.py::test_route_json_scores_carry_pricing_tier`).
- [x] Skill documents both modes, the decomposition protocol, and the
      unconditional high-risk gate.
- [x] Generic snippet installs by paste into any instruction file — no code.

**Completion criteria:** installing the skill into a host requires zero code
changes to AgentRouter — met (instructions + existing JSON contract only).

**Risks:** host model lineups change names → mapping is by *tier*, not model
name, so the skill survives model churn.

---

## Dependency graph

```
M1 ──▶ M2 ──▶ M3
 │      │       │
 │      └──▶ M4 ──▶ M5
 │              
 └────────────▶ (M4 also needs M1's log)
        M2,M3 ──▶ M6 ──▶ M7 ◀── M5
        M1–M4 ──▶ M8 (skill layer; consumes route --json)
```
