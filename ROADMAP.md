# AgentRouter OS — Roadmap

> **Purpose:** Sequence delivery across the four scope tiers used throughout the
> docs — **MVP → Capstone demo → Advanced → Production-future** — expanded into
> concrete phases. Each phase lists its goal and headline deliverables.
> Milestone-level tasks, validation, and risks are in
> [MILESTONES.md](MILESTONES.md) (1:1 with these phases).

---

## Phase 1 — MVP (CLI: classify + recommend)  · tier: **MVP**

**Goal:** A working CLI that turns a task into an explainable recommendation
with a fallback, a generated prompt, and a safety checklist, over static YAML
registries, logging every decision.

**Deliverables**
- `init`, `route`, `explain` (basic), `registry list`, `prompt generate`.
- TaskClassifier (7 dimensions, rule-based).
- Pydantic-validated `models.yaml` / `providers.yaml`.
- RoutingEngine scoring + eligibility filters + fallback selection.
- SafetyEngine checklists + risk gating (no auto-execute).
- PromptGenerator.
- SQLite DecisionLog.
- Seed registry covering all six provider *types* (static entries).

**Done when:** all MVP acceptance criteria in [PRD.md](PRD.md) pass.

---

## Phase 2 — Capstone demo (polished multi-provider showcase)  · tier: **Capstone demo**

**Goal:** A demo-ready tool that syncs live model catalogs and shows off
multi-provider routing with rich explanations.

**Deliverables**
- `providers refresh` wired to all six adapters (`refresh_models`).
- Read-only auth for catalog fetch (API-key providers).
- Rich `explain` (full score table, weight shifts, eligibility breakdown).
- Polished CLI output/formatting; `--json` everywhere.
- Larger, realistic seed registry.

**Done when:** `providers refresh` updates the registry live with no code
change, and a scripted demo routes several task types across ≥3 real providers.

---

## Phase 3 — Adapter expansion  · tier: **Capstone demo → Advanced**

**Goal:** Broaden and harden provider coverage.

**Deliverables**
- Generic CLI-agent adapter reads user config for arbitrary local agents.
- Robust capability mapping + idempotent refresh + staleness warnings
  (`last_updated`).
- Adapter test harness (mock provider responses).

**Done when:** adding a new provider requires only a new adapter + YAML entry,
verified by adding one end-to-end.

---

## Phase 4 — Advanced: feedback learning loop  · tier: **Advanced**

**Goal:** The router improves from real outcomes.

**Deliverables**
- `feedback` command + FeedbackStore.
- Weight-adaptation logic (bounded nudges to `w_cap/w_cost/w_lat/w_ctx`).
- Acceptance-rate + drift reporting.

**Done when:** feedback measurably shifts subsequent recommendations in a
controlled test, within safe bounds.

---

## Phase 5 — Advanced: web dashboard  · tier: **Advanced**

**Goal:** Visibility into routing history and cost trends.

**Deliverables**
- FastAPI read-only API over DecisionLog/FeedbackStore.
- Dashboard: decision history, acceptance rate, cost-tier distribution.

**Done when:** dashboard renders live from the local DB with no write path to
routing.

---

## Phase 6 — Production-future: execution automation  · tier: **Production-future**

**Goal:** Optionally run the recommended tool, safely.

**Deliverables**
- Real `execute` in adapters where feasible (starting with the strongest
  execution target).
- Auth/secret management.
- Hard enforcement that `risk=high` never auto-executes without human approval.

**Done when:** a low-risk task can be executed end-to-end from the CLI, with
high-risk tasks provably gated.

---

## Phase 7 — Production-future: teams & telemetry  · tier: **Production-future**

**Goal:** Multi-user, governed deployment.

**Deliverables**
- Shared registry + team config.
- Usage telemetry, cost dashboards, policy controls.
- Hosting story beyond single-user local.

**Done when:** a team shares one registry and policy, with per-user history and
aggregate cost reporting.

---

## Phase 8 — Production-future: agent skill integration  · tier: **Production-future**

**Goal:** AgentRouter works *inside* any agent CLI/IDE (Claude Code, Codex,
Antigravity, Cursor, …) as a skill/instruction protocol — the host agent
decomposes tasks, AgentRouter routes each subtask to a pricing tier, the host
runs each subtask on its cheapest adequate model.

**Deliverables**
- Portable Claude Code skill (auto/manual modes, decomposition protocol,
  tier→host-model mapping, unconditional high-risk gate).
- Host-agnostic `AGENTS.md` protocol snippet for skill-less hosts.
- `pricing_tier` in `route --json` score rows (the field hosts map on).
- Per-host install docs.

**Done when:** installing into a new host requires only pasting instructions —
zero AgentRouter code changes.

---

## Phase → tier map

| Phase | Tier |
|---|---|
| 1 MVP | MVP |
| 2 Capstone demo | Capstone demo |
| 3 Adapter expansion | Capstone demo → Advanced |
| 4 Feedback loop | Advanced |
| 5 Web dashboard | Advanced |
| 6 Execution automation | Production-future |
| 7 Teams & telemetry | Production-future |
| 8 Agent skill integration | Production-future |
