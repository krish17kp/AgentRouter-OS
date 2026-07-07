# AgentRouter OS — Business Requirements Document (BRD)

> **Purpose:** Frame the business case — the problem worth solving, who pays for
> it in time or money, and why this approach wins. Scope tiers used throughout:
> **MVP → Capstone demo → Advanced → Production-future.**

---

## 1. Business problem

Organizations and individuals now use a portfolio of AI tools (Claude Code,
Cursor, OpenAI, OpenRouter, local agents) but have **no systematic way to route
work to the right one.** The result is:

- **Wasted spend** — frontier-priced models used for trivial work.
- **Wasted quality** — weak models used for high-stakes work, causing rework.
- **Decision drift** — every new model release invalidates yesterday's habits.
- **Uncontrolled risk** — sensitive tasks (auth, payments, prod) routed without
  consistent safety gating.

The market lacks a **neutral, provider-agnostic, continuously-updatable**
routing layer. Vendor-native tooling is inherently biased toward its own models.

## 2. Target users / buyers

| Segment | Who | Why they care |
|---|---|---|
| **Individual developers** | Multi-tool AI power users | Save time and money per task |
| **Engineering teams** | Leads standardizing AI usage | Consistent, auditable routing policy |
| **AI/platform teams** | Build internal agent tooling | Programmatic classification + registry they control |
| **FinOps / eng managers** | Own AI budgets | Prevent overspend, get usage visibility |

## 3. Value proposition

> **The right AI for every task — and it stays right as the models change.**

- **Neutral:** compares across providers, not within one vendor.
- **Obsolescence-proof:** the routing logic is stable; the model catalog is
  data you own and refresh. Tomorrow's model works today with a config edit.
- **Explainable:** every recommendation shows its reasoning and can be audited.
- **Safe by default:** risk-aware gating built into the routing decision.
- **Low friction:** one CLI command; no platform migration required.

## 4. Use cases

- **UC-1 Daily task routing** — dev pastes a task, gets tool + fallback + prompt. *(MVP)*
- **UC-2 Cost control** — trivial tasks routed to cheaper tiers automatically. *(MVP)*
- **UC-3 Risk gating** — high-risk tasks flagged with approval + checklist. *(MVP)*
- **UC-4 Fast model adoption** — new model added via YAML, instantly routable. *(MVP)*
- **UC-5 Live catalog sync** — `providers refresh` keeps the model list current. *(Capstone demo)*
- **UC-6 Decision audit** — `explain <id>` justifies a past routing choice. *(Capstone demo)*
- **UC-7 Continuous improvement** — feedback tunes routing to real outcomes. *(Advanced)*
- **UC-8 Team visibility** — dashboard shows routing + cost trends. *(Advanced)*
- **UC-9 One-click execution** — run the recommended tool directly. *(Production-future)*

## 5. Business outcomes

| Outcome | Indicator |
|---|---|
| Lower AI spend | Fewer trivial tasks on frontier-tier models |
| Higher output quality | Fewer reworks on high-stakes tasks |
| Faster model adoption | Time-to-routable for a new model measured in minutes |
| Reduced incident risk | High-risk tasks consistently gated |
| Better governance | 100% of routing decisions logged and auditable |

## 6. Differentiation

| Alternative | Gap AgentRouter OS fills |
|---|---|
| **Vendor-native routers** (single provider) | Biased to one catalog; AgentRouter is neutral across all. |
| **Manual/gut-feel routing** | No consistency, no audit trail, no safety gating. |
| **Static "best model" blog posts** | Stale within weeks; AgentRouter's registry is live data. |
| **General LLM gateways** (proxy/load-balance) | Optimize routing for *serving*, not *task-fit + safety planning*. |

**Moat:** the separation of stable *logic* from data-driven *catalog*, plus a
feedback loop that improves fit over time — hard to replicate with hardcoded,
vendor-locked tools.

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Registry goes stale | Bad recommendations | `providers refresh` (Capstone); clear "last updated" metadata |
| Subjective ability scores | Debatable rankings | Transparent scoring + feedback loop (Advanced) to correct over time |
| Scope creep into execution | Delays MVP, adds risk | Hard v1 boundary: planner only, adapters interface-only |
| Provider API changes | Refresh breaks | Adapter isolation — one provider change touches one adapter |
| Over-trust in advisory output | Users skip judgment | Explicit "advisory, not benchmark" limitation messaging |
| Secret handling (later tiers) | Security exposure | No live credentials until Production-future, with dedicated secret mgmt |

## 8. Success definition

MVP is a business success when a user routinely runs `route` before starting AI
tasks, trusts the recommendation enough to act on it without override in the
majority of cases, and can add a brand-new model without engineering help.
