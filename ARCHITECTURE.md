# AgentRouter OS — Architecture

> **Purpose:** Describe the system's components, how data flows through them, and
> the end-to-end lifecycle of a `route` request. Scope tiers:
> **MVP → Capstone demo → Advanced → Production-future.**
>
> The model-entry schema referenced here is defined authoritatively in
> [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md). Adapter method names come
> from [PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md). CLI command names
> come from [CLI_SPEC.md](CLI_SPEC.md).

---

## 1. System overview

AgentRouter OS is a layered Python application. A thin **CLI** drives a
**RoutingEngine** that orchestrates stateless components (classify → score →
generate → gate) over two **data-driven registries**, and writes results to a
local **store**. Providers are pluggable via **adapters**. A **web API** is a
future read-only surface over the same store.

```
                          ┌──────────────────────────────────────────┐
        user task ───────▶│                  CLI (Typer)              │
                          │  init · route · explain · feedback ·       │
                          │  registry list · providers refresh ·      │
                          │  prompt generate                          │
                          └───────────────┬──────────────────────────┘
                                          │
                                          ▼
                          ┌──────────────────────────────────────────┐
                          │              RoutingEngine                │  orchestrator
                          └──┬───────┬──────────┬──────────┬──────────┘
                             │       │          │          │
             ┌───────────────▼┐ ┌────▼──────┐ ┌─▼────────┐ ┌▼────────────┐
             │ TaskClassifier │ │  Scoring  │ │ Prompt   │ │  Safety     │
             │ (7 dimensions) │ │  (rules)  │ │ Generator│ │  Engine     │
             └───────┬────────┘ └────┬──────┘ └────┬─────┘ └────┬────────┘
                     │               │             │            │
                     │        reads  ▼             │            │
                     │      ┌───────────────────────────────┐   │
                     │      │   Model Registry (YAML/JSON)   │   │
                     │      │   Provider Registry (YAML)     │   │
                     │      │   validated by Pydantic v2     │   │
                     │      └───────────────┬───────────────┘   │
                     │                      │ refresh_models     │
                     │            ┌─────────▼──────────┐         │
                     │            │  Provider Adapters │         │
                     │            │ claude-code·openai │         │
                     │            │ openrouter·cursor  │         │
                     │            │ cli-agent·manual   │         │
                     │            └─────────┬──────────┘         │
                     │                      │ execute (v1: N/A)  │
                     │            ┌─────────▼──────────┐         │
                     │            │ ExecutionAdapter   │◀────────┘  interface only in v1
                     │            │   (interface)      │
                     │            └────────────────────┘
                     ▼
        ┌────────────────────────────────────────────┐
        │      Storage Layer  (SQLite)                │
        │   DecisionLog  +  FeedbackStore             │
        └───────────────┬────────────────────────────┘
                        │ (read-only)
                        ▼
        ┌────────────────────────────────────────────┐
        │   Web API / Dashboard (FastAPI) — future    │  Advanced tier
        └────────────────────────────────────────────┘
```

---

## 2. Components

### 2.1 CLI (Typer) — *MVP*
Entry point. Maps commands to RoutingEngine calls, formats output, sets exit
codes. Owns no business logic. Commands defined in [CLI_SPEC.md](CLI_SPEC.md).

### 2.2 RoutingEngine — *MVP*
The orchestrator. For a `route` call it runs, in order: classify → load eligible
models → score → select recommendation + fallback → generate prompt → build
safety checklist → persist decision. Pure coordination; delegates all real work.

### 2.3 TaskClassifier — *MVP*
Turns free-text into the 7 canonical dimensions: `task_type`, `complexity`,
`risk`, `context_size`, `output_type`, `tool_needs`, `approval_level`. In MVP
this is a rule/heuristic classifier (keyword + pattern signals). Inference rules
live in [ROUTING_RULES.md](ROUTING_RULES.md). Output is a Pydantic
`Classification` model.

### 2.4 ProviderRegistry — *MVP (static) / Capstone (refreshable)*
Loads `providers.yaml`: each provider's id, adapter type, auth model, and
execution support. Source of which adapters to instantiate.

### 2.5 ModelRegistry — *MVP (static) / Capstone (refreshable)*
Loads `models.yaml` (or JSON). Each entry conforms to the schema in
[MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md). **This is the single
source of truth for model capabilities.** No component redefines these fields;
they all read them. Validated by Pydantic on load — malformed entries fail
loudly (NFR-5).

### 2.6 RoutingEngine → Scoring — *MVP*
Computes each eligible model's score from classification + registry metadata
using the documented formula (capability match, cost/latency fit, context fit,
minus risk penalty; hard disqualification on context and safety). Full formula
in [ROUTING_RULES.md](ROUTING_RULES.md).

### 2.7 PromptGenerator — *MVP*
Builds a tool-tailored execution prompt from the task + recommendation (e.g. a
Claude Code prompt vs. a Cursor prompt differ in framing). Templated, not
model-specific-hardcoded.

### 2.8 SafetyEngine — *MVP*
Maps `risk` + `approval_level` to a safety checklist and gating flags. Enforces
NFR-8: high-risk tasks never carry an auto-execute flag. Independent of which
model was chosen.

### 2.9 Provider Adapters — *MVP (interface) / Capstone (live refresh)*
One class per provider implementing the adapter contract (`list_models`,
`refresh_models`, `map_capabilities`, `supports_execution`, `execute`). They
translate provider-specific model info into the registry schema. Full spec:
[PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md).

### 2.10 ExecutionAdapter (interface) — *interface in v1, live in Production-future*
The `execute` method exists on the contract but raises `NotSupported` in v1.
This preserves the boundary "planner, not executor" while keeping the seam ready.

### 2.11 Storage Layer — *MVP*
SQLite. **DecisionLog** stores each decision (raw task, classification, ranked
scores, recommendation, fallback, generated prompt, checklist, timestamp,
`decision_id`). **FeedbackStore** stores outcome ratings keyed to `decision_id`
(populated by `feedback`, consumed by the Advanced learning loop).

### 2.12 Web API / Dashboard (FastAPI) — *Advanced*
Read-only views over DecisionLog/FeedbackStore (history, cost trends,
acceptance rate). No write path to routing in v1 of the dashboard.

---

## 3. Request lifecycle (`route "<task>"`)

1. **CLI** parses the task string and flags, calls `RoutingEngine.route(task)`.
2. **TaskClassifier** produces a `Classification` (7 dimensions).
3. **RoutingEngine** loads models from **ModelRegistry**, filters to those whose
   `deprecation_status` is active and whose `context_window` fits `context_size`
   (hard disqualification — FR-5).
4. **Scoring** ranks the survivors via the formula in ROUTING_RULES.md.
5. **RoutingEngine** picks rank 1 = recommendation, rank 2 = fallback (applying
   fallback rules: prefer a different cost/latency profile or the entry's
   declared `fallback` mapping).
6. **SafetyEngine** derives the checklist + gating flags from `risk` /
   `approval_level`.
7. **PromptGenerator** builds the execution prompt for the recommended tool.
8. **Storage Layer** writes the full decision, returns `decision_id`.
9. **CLI** prints classification, ranked recommendation + fallback, prompt
   pointer, checklist, and `decision_id`.

`explain <id>` re-reads the DecisionLog row and re-renders steps 2–8 without
recomputation. `feedback <id>` appends to FeedbackStore (and, in Advanced,
nudges scoring weights). `providers refresh` (Capstone) calls each adapter's
`refresh_models` and rewrites the ModelRegistry data.

---

## 4. Design principles

- **Logic stable, catalog dynamic.** Engine code never names a specific current
  model; all model facts come from the registry (NFR-2).
- **One source of truth.** The model schema lives in one doc/one Pydantic model;
  everything reads it.
- **Adapter isolation.** A provider API change touches exactly one adapter.
- **Fail loud at the boundary.** Registry validation on load; no silent defaults.
- **Planner not executor (v1).** Execution seam exists but is inert.
