# AgentRouter OS — Product Requirements Document (PRD)

> **Purpose:** Define what AgentRouter OS must do, for whom, and how we know it
> works. Scope is tagged per requirement using the shared tiers
> **MVP → Capstone demo → Advanced → Production-future.**

---

## 1. Vision

Every AI-assisted task should be routed to the tool best suited for it, with a
transparent reason and a safe execution plan — and that routing must stay
correct as models are released, repriced, and retired. AgentRouter OS is the
neutral, data-driven decision layer that makes "which AI should do this?" a
one-command, explainable question.

## 2. Target users

| User | Context | Primary need |
|---|---|---|
| **Individual developer** | Uses several AI tools daily | Stop guessing which model/tool fits each task |
| **AI-heavy team lead** | Standardizes tooling for a team | Consistent, explainable routing policy |
| **Prompt/agent engineer** | Builds agent workflows | Programmatic classification + prompt scaffolds |
| **Cost-conscious operator** | Watches AI spend | Avoid overpaying frontier prices for trivial tasks |

## 3. Pain points

- No neutral cross-provider comparison; each vendor markets its own model.
- Model landscape changes faster than anyone's mental model.
- Easy to overspend (frontier model for a one-liner) or underspend (weak model
  for a high-risk refactor).
- Risky tasks (auth, prod, payments) get no consistent safety gating.
- Tool/context/vision requirements are judged by feel, not checked.

## 4. User stories

- **US-1** — As a developer, I run `route "<task>"` and get a recommended tool +
  fallback with a plain-English reason, so I can start immediately. *(MVP)*
- **US-2** — As a developer, I get a generated execution prompt tailored to the
  recommended tool, so I don't hand-write scaffolding. *(MVP)*
- **US-3** — As a cautious developer, high-risk tasks come with a safety
  checklist and no silent auto-execution. *(MVP)*
- **US-4** — As a team lead, I edit a YAML file to add a newly released model
  and it's immediately routable, with no code change. *(MVP)*
- **US-5** — As an operator, I run `providers refresh` to sync the live model
  list from each provider. *(Capstone demo)*
- **US-6** — As an analyst, I run `explain <id>` to see the full scoring
  breakdown behind a past decision. *(Capstone demo)*
- **US-7** — As a returning user, I run `feedback <id>` and the router adjusts
  future recommendations based on outcomes. *(Advanced)*
- **US-8** — As a team, we view routing history and cost trends in a web
  dashboard. *(Advanced)*
- **US-9** — As a power user, the recommended tool can actually be executed from
  the CLI. *(Production-future)*

## 5. MVP scope

**In:** task classification (7 dimensions), scoring against a static YAML
registry, ranked recommendation + one fallback, generated execution prompt,
risk-based safety checklist, decision logging to SQLite, and the commands
`init`, `route`, `explain` (basic), `registry list`, `prompt generate`.

**Out (deferred):** live `providers refresh`, feedback learning, web dashboard,
real execution, auth/secrets, multi-user.

## 6. Functional requirements

| ID | Requirement | Tier |
|---|---|---|
| **FR-1** | Classify a free-text task into the 7 dimensions: `task_type`, `complexity`, `risk`, `context_size`, `output_type`, `tool_needs`, `approval_level`. | MVP |
| **FR-2** | Load provider + model registries from YAML/JSON, validated by Pydantic; reject malformed entries with a clear error. | MVP |
| **FR-3** | Score every eligible model with the documented formula and rank them. | MVP |
| **FR-4** | Return exactly one recommendation and one fallback (or state none qualifies). | MVP |
| **FR-5** | Disqualify models whose `context_window` cannot fit the estimated task context. | MVP |
| **FR-6** | Apply risk-based safety gates (e.g. high risk → no auto-execute, human approval flag). | MVP |
| **FR-7** | Generate an execution prompt tailored to the recommended tool. | MVP |
| **FR-8** | Produce a safety checklist scaled to the task's risk level. | MVP |
| **FR-9** | Persist each decision (input, classification, scores, outputs) to SQLite with a stable `decision_id`. | MVP |
| **FR-10** | `registry list` prints the loaded models with key attributes. | MVP |
| **FR-11** | `explain <id>` reconstructs the classification + scoring rationale for a logged decision. | MVP (basic) / Capstone (rich) |
| **FR-12** | `providers refresh` calls each adapter's `refresh_models` and updates the model registry. | Capstone demo |
| **FR-13** | Support all six adapters: Claude Code, OpenAI, OpenRouter, Cursor, generic CLI, manual. | Capstone demo |
| **FR-14** | `feedback <id>` records an outcome rating and adjusts scoring weights. | Advanced |
| **FR-15** | Read-only web dashboard over the decision log. | Advanced |
| **FR-16** | Execute the recommended tool via an adapter's `execute`. | Production-future |

## 7. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| **NFR-1 Speed** | `route` returns in interactive time on a static registry. | < 1s local (no network) |
| **NFR-2 Obsolescence-safety** | No current model name appears in routing logic; only in registry data. | 0 hardcoded models in code paths |
| **NFR-3 Extensibility** | Add a new provider = new adapter class; add a new model = YAML edit. | No engine changes required |
| **NFR-4 Explainability** | Every recommendation carries a reproducible score breakdown. | 100% of decisions explainable |
| **NFR-5 Data integrity** | Malformed registry entries fail loudly at load, never silently. | Validation on 100% of entries |
| **NFR-6 Portability** | Runs from a single Python install + local SQLite file. | No external services in MVP |
| **NFR-7 Auditability** | Every decision is logged and retrievable by id. | 100% of `route` calls logged |
| **NFR-8 Safety** | High-risk tasks never auto-execute in any tier without explicit approval. | Enforced by SafetyEngine |

## 8. Success metrics

- **Adoption:** user runs `route` on the majority of AI tasks in a week.
- **Trust:** ≥80% of recommendations accepted without override (measured via `feedback`).
- **Freshness:** a newly released model is routable within minutes of a registry edit.
- **Cost fit:** measurable reduction in trivial tasks sent to frontier-tier models.
- **Explainability:** every `explain <id>` reproduces the original decision.

## 9. Acceptance criteria (per key FR)

- **FR-1:** Given three sample tasks (trivial script, high-risk auth refactor,
  long-doc summary), the classifier assigns plausible values to all 7 dimensions.
- **FR-2:** A YAML entry missing a required field (e.g. `context_window`) causes
  a validation error naming the field; valid entries load.
- **FR-4:** `route` on any task returns ≥1 recommendation and ≤1 fallback, or an
  explicit "no eligible model" message.
- **FR-5:** A task estimated at 200k tokens excludes every model whose
  `context_window` < 200k from recommendation.
- **FR-6/FR-8:** A task classified `risk=high` yields `approval_level =
  human-approval-required` and a checklist with ≥3 risk-specific items.
- **FR-9/FR-11:** After `route`, `explain <id>` returns the same classification
  and score ordering that `route` printed.
- **FR-12:** `providers refresh` updates the model registry from adapters
  without editing any code.
