# AgentRouter OS — Routing Rules

> **Purpose:** Define exactly how a task is classified, how models are scored,
> how risk gates fire, how context-size filtering works, and how a fallback is
> chosen. These rules are the stable *logic* of the system; they read model
> facts from [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md) but never name
> a specific current model.
>
> Scope: classification + scoring + fallback + risk gating are **MVP**. Weight
> adaptation from feedback is **Advanced**.

---

## 1. Classification — the 7 dimensions

The TaskClassifier maps free text to these canonical fields (the same seven used
everywhere in the docs):

| Dimension | Values | How it's inferred (MVP: rules/heuristics) |
|---|---|---|
| `task_type` | `coding` \| `reasoning` \| `writing` \| `analysis` \| `summarization` \| `general` | Keyword + verb signals ("refactor/debug"→coding; "summarize"→summarization; "analyze/compare"→analysis). |
| `complexity` | `low` \| `medium` \| `high` | Scope signals: #steps, #files, breadth of ask, presence of "and"-chained subtasks. |
| `risk` | `low` \| `medium` \| `high` | Sensitivity signals: auth, payments, prod, deletion, migrations, secrets → high. |
| `context_size` | estimated tokens (int) → band `small`\|`medium`\|`large` | Estimated from referenced files/inputs; drives the hard context filter. |
| `output_type` | `code` \| `text` \| `code+tests` \| `data` \| `plan` | Inferred from the deliverable requested. |
| `tool_needs` | subset of `tool-use`,`file-edit`,`shell`,`web`,`vision`,`function-calling` | "edit files"→file-edit; "run"→shell; "image"→vision; etc. |
| `approval_level` | `auto` \| `notify` \| `human-approval-required` | Derived from `risk` (see §4). |

Classifier output is a validated `Classification` object. In the Advanced tier a
model-assisted classifier can supplement the heuristics; the dimensions and
downstream contract stay identical.

---

## 2. Eligibility filters (hard, before scoring)

A model is **disqualified** (never recommended) if any holds:

1. `deprecation_status == retired`.
2. `context_window < estimated task tokens` (context doesn't fit) — FR-5.
3. A required `tool_needs` capability is absent from `tool_support`
   (e.g. task needs `file-edit` but model lacks it).
4. Task needs `vision` but `vision_support == false`.

Survivors proceed to scoring. If none survive, `route` reports "no eligible
model" and recommends the manual-agent entry.

---

## 3. Scoring formula

For each eligible model:

```
score =  w_cap  * capability_match
       + w_cost * cost_fit
       + w_lat  * latency_fit
       + w_ctx  * context_fit
       + use_case_adjust
       - risk_penalty
       - deprecation_penalty
```

**Terms (all normalized 0–1 unless noted):**

- `capability_match` — the `ability.*` score aligned to `task_type`, /10.
  Coding tasks weight `ability.coding`; reasoning/analysis weight
  `ability.reasoning`; writing/summarization weight `ability.writing`. Mixed
  tasks blend.
- `cost_fit` — higher when `pricing_tier` matches the task's cost tolerance.
  Trivial/`complexity=low` tasks reward cheaper tiers; `complexity=high` tasks
  tolerate `frontier`.
- `latency_fit` — higher when `latency_tier` suits the task (interactive work
  rewards `fast`; batch/large work tolerates `slow`).
- `context_fit` — rewards models that fit the context with headroom without
  massive over-provisioning (fits comfortably > barely fits > vastly oversized).
- `use_case_adjust` — `+` if `task_type` ∈ `ideal_use_cases`; `−` if ∈
  `avoid_use_cases`.
- `risk_penalty` — **not** applied to capability; risk drives *gating* (§4), not
  model down-ranking, except a small preference for higher-`ability` models on
  `risk=high` tasks (don't send high-risk work to a weak model).
- `deprecation_penalty` — applied if `deprecation_status == deprecated`.

**Default weights (MVP, tunable; Advanced adapts them from feedback):**

| Weight | Default | Shifts when |
|---|---|---|
| `w_cap` | 0.45 | ↑ for `complexity=high` / `risk=high` |
| `w_cost` | 0.25 | ↑ for `complexity=low` |
| `w_lat` | 0.15 | ↑ for interactive/`fast`-desired tasks |
| `w_ctx` | 0.15 | ↑ for `context_size=large` |

The **recommendation** is the highest score; the **fallback** is chosen per §5.

---

## 4. Risk levels and safety gates

Risk sets `approval_level` and the SafetyEngine's checklist. Risk gates behavior;
it does not silently pick a different model.

| `risk` | `approval_level` | Gates (SafetyEngine) | Checklist emphasis |
|---|---|---|---|
| `low` | `auto` | none | Basic sanity review |
| `medium` | `notify` | Flag for review before acting | Review output, test, check scope |
| `high` | `human-approval-required` | **No auto-execute in any tier (NFR-8)**; explicit human sign-off | Diff review, run tests, secret scan, backup/rollback, blast-radius check |

High-risk triggers (any → `risk=high`): authentication/authorization, payments/
billing, production systems, data deletion/migration, secrets/credentials,
infrastructure changes.

---

## 5. Fallback selection

The fallback is the "if the recommendation doesn't work out" option. Selected in
this order:

1. If the recommended model's `fallback` list names an **eligible** model, take
   the first such entry.
2. Otherwise, the highest-scoring eligible model that **differs meaningfully**
   from the recommendation (different provider *or* a lower `pricing_tier`),
   giving the user a genuine alternative rather than a near-clone.
3. If only one model is eligible, the manual-agent entry is the fallback.

---

## 6. Worked examples

**A. Trivial script**
`route "write a bash one-liner to count lines in a file"`
→ `task_type=coding, complexity=low, risk=low, context_size=small, tool_needs=[]`
→ `w_cost` boosted → recommends a cheap `low`/`fast` tier model; fallback a
different cheap provider. `approval_level=auto`, minimal checklist.

**B. High-risk refactor** (README example)
`route "Refactor auth to JWT rotation and add tests"`
→ `coding, high, high, medium, code+tests, [file-edit, shell]`
→ eligibility drops models lacking `file-edit`; `w_cap` boosted; a
frontier-coding model wins; fallback a strong-coding model at lower cost.
`approval_level=human-approval-required`, 5-item safety checklist, no auto-execute.

**C. Long-document summary**
`route "Summarize this 300k-token filing into 10 bullets"`
→ `summarization, medium, low, large (~300k), text, []`
→ context filter excludes any model with `context_window < 300000`; `w_ctx` and
`ability.writing` dominate; recommends a large-context writing-strong model.
`approval_level=auto`.

**D. Vision task**
`route "Describe what's wrong in this UI screenshot"`
→ `analysis, low, low, small, text, [vision]`
→ eligibility keeps only `vision_support: true` models; recommends the
best-scoring one; fallback another vision model or manual-agent.
