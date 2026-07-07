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

**Validation checklist**
- [ ] `init` creates config + registries + DB.
- [ ] `route` returns ≥1 recommendation + ≤1 fallback for the three sample tasks (script / auth refactor / long summary).
- [ ] Malformed YAML entry → exit code 3 naming the field (FR-2).
- [ ] 300k-token task excludes sub-300k-context models (FR-5).
- [ ] `risk=high` → `human-approval-required` + ≥3 checklist items, no auto-execute flag (FR-6/8).
- [ ] `explain <id>` reproduces the printed decision (FR-11).
- [ ] No current model name appears in engine code (NFR-2).

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

**Validation checklist**
- [ ] `providers refresh` updates the registry with no code change (FR-12).
- [ ] Refresh is idempotent (re-run → no duplicates).
- [ ] `explain` shows full eligibility + score breakdown.
- [ ] Demo routes ≥4 task types across ≥3 real providers.

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

**Validation checklist**
- [ ] A brand-new provider added via new adapter + YAML only, routable end-to-end.
- [ ] Stale entries surface a warning.
- [ ] Adapter tests pass against mocked responses.

**Completion criteria:** "new provider = new adapter + YAML, zero engine change" demonstrated.

**Risks:** inconsistent upstream metadata → conservative defaults + validation.

---

## M4 — Feedback learning loop  · tier: **Advanced**  · depends on: M1 (log), M2

**Goal:** Recommendations improve from logged outcomes.

**Tasks**
- `feedback` command + FeedbackStore schema.
- Bounded weight-adaptation from ratings/accept-override signals.
- Acceptance-rate + drift reporting.

**Outputs:** feedback pipeline; adaptive weights.

**Validation checklist**
- [ ] `feedback` persists and links to a `decision_id`.
- [ ] Repeated negative feedback shifts weights within bounds.
- [ ] Weight changes are logged and reversible.

**Completion criteria:** feedback measurably changes later recommendations in a controlled test.

**Risks:** overfitting to sparse feedback → clamp nudge size; require minimum sample.

---

## M5 — Web dashboard  · tier: **Advanced**  · depends on: M1 (log), M4 (optional)

**Goal:** Read-only visibility over decisions and trends.

**Tasks**
- FastAPI read-only endpoints over DecisionLog/FeedbackStore.
- Dashboard views: history, acceptance rate, cost-tier distribution.

**Outputs:** dashboard app.

**Validation checklist**
- [ ] Dashboard renders live from local DB.
- [ ] No write path from dashboard into routing.

**Completion criteria:** dashboard usable against a populated DB.

**Risks:** scope creep into a full web app → keep strictly read-only in this tier.

---

## M6 — Execution automation  · tier: **Production-future**  · depends on: M2, M3

**Goal:** Optionally run the recommended tool, with hard safety gating.

**Tasks**
- Implement real `execute` for the strongest execution-capable adapter first.
- Auth/secret management.
- Enforce: `risk=high` never auto-executes without human approval (NFR-8).

**Outputs:** execution path; secret handling.

**Validation checklist**
- [ ] A `risk=low` task executes end-to-end from the CLI.
- [ ] A `risk=high` task is provably blocked from auto-execution.
- [ ] No secrets logged or committed.

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

**Validation checklist**
- [ ] Team shares one registry + policy.
- [ ] Per-user history + aggregate cost reporting available.
- [ ] Policy controls enforce routing/safety rules org-wide.

**Completion criteria:** a team operates from shared config with per-user history and cost visibility.

**Risks:** multi-tenant complexity → phase carefully after single-user is solid.

---

## Dependency graph

```
M1 ──▶ M2 ──▶ M3
 │      │       │
 │      └──▶ M4 ──▶ M5
 │              
 └────────────▶ (M4 also needs M1's log)
        M2,M3 ──▶ M6 ──▶ M7 ◀── M5
```
