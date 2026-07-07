# AgentRouter OS — Model Registry Schema

> **Purpose:** Define the authoritative schema for a model entry. This is the
> **single source of truth** for model capabilities across the system — the
> ModelRegistry, RoutingEngine scoring, and every adapter's `map_capabilities`
> all conform to the fields defined here. No other document redefines these
> fields; they reference this one.
>
> **Governing principle:** models live in editable YAML/JSON data, never in
> code. Adding, repricing, or deprecating a model is a **data edit**, not a code
> change (NFR-2, NFR-3). Model names in this doc are **illustrative placeholders
> only** — they carry no permanent meaning in routing logic.

---

## 1. Where it lives

- `registry/models.yaml` — the model catalog (one list of model entries).
- `registry/providers.yaml` — the provider catalog (see PROVIDER_ADAPTER_SPEC).
- Both are validated by **Pydantic v2** at load. A malformed or incomplete entry
  raises a validation error naming the offending field; nothing loads silently.

---

## 2. Model entry fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `provider` | string | yes | Provider id; must exist in `providers.yaml`. |
| `model_id` | string | yes | Provider-native identifier (opaque; not parsed for meaning). |
| `display_name` | string | no | Human label for output. Defaults to `model_id`. |
| `context_window` | int (tokens) | yes | Total context the model accepts. Used for hard context-fit disqualification. |
| `max_input_tokens` | int | no | Input cap if distinct from `context_window`. |
| `max_output_tokens` | int | yes | Maximum generated tokens. |
| `pricing_tier` | enum: `free`\|`low`\|`medium`\|`high`\|`frontier` | yes | Relative cost band (not exact $). Keeps routing stable as prices change. |
| `latency_tier` | enum: `fast`\|`medium`\|`slow` | yes | Relative responsiveness band. |
| `ability` | object | yes | Capability scores (see below). |
| `ability.coding` | int 0–10 | yes | Coding/refactoring/debugging strength. |
| `ability.reasoning` | int 0–10 | yes | Multi-step reasoning / analysis strength. |
| `ability.writing` | int 0–10 | yes | Long-form / creative / doc writing strength. |
| `tool_support` | list[string] | yes | Capabilities: e.g. `tool-use`, `file-edit`, `shell`, `web`, `function-calling`. Empty list = none. |
| `vision_support` | bool | yes | Accepts image input. |
| `ideal_use_cases` | list[string] | no | Task types this model is preferred for (routing hint / boost). |
| `avoid_use_cases` | list[string] | no | Task types to route away from (routing hint / penalty). |
| `deprecation_status` | enum: `active`\|`deprecated`\|`retired` | yes | `active` = routable. `deprecated` = penalized. `retired` = excluded. |
| `fallback` | list[string] | no | Ordered `model_id`s to prefer as fallback when this model is chosen but unsuitable/unavailable. |
| `notes` | string | no | Free text (e.g. "preview", "region-limited"). |
| `source` | enum: `manual`\|`refresh` | no | Whether the entry was hand-authored or written by `providers refresh`. |
| `last_updated` | date (ISO) | no | When capability data was last verified. Drives staleness warnings. |

### Field usage in routing
- `context_window` → **hard filter** (FR-5): model excluded if it can't fit the task's `context_size`.
- `deprecation_status` → `retired` excluded; `deprecated` penalized.
- `ability.*` → capability-match term, weighted by the task's `task_type`.
- `tool_support` / `vision_support` → hard requirement if the task's `tool_needs` demands them.
- `pricing_tier` / `latency_tier` → cost/latency fit terms (weight varies by task).
- `ideal_use_cases` / `avoid_use_cases` → score boost/penalty.
- `fallback` → seeds fallback selection.

Exact formula: [ROUTING_RULES.md](ROUTING_RULES.md).

---

## 3. Validation rules

- `provider` MUST reference a provider defined in `providers.yaml`.
- `model_id` MUST be unique within a provider.
- `ability.*` MUST be integers 0–10; out-of-range fails validation.
- `pricing_tier`, `latency_tier`, `deprecation_status` MUST be one of their enums.
- `context_window`, `max_output_tokens` MUST be positive integers.
- Every `fallback` entry SHOULD resolve to a known `model_id` (unresolved →
  load-time warning, not fatal, so a fallback can be added before its target).
- Unknown fields → validation error (no silent extras).

---

## 4. Annotated example entry (YAML)

```yaml
# registry/models.yaml
# NOTE: model_id values below are ILLUSTRATIVE PLACEHOLDERS.
# The routing engine never keys logic off a specific name — only off the fields.
models:
  - provider: claude-code                 # must exist in providers.yaml
    model_id: "<frontier-coding-model>"    # opaque native id
    display_name: "Frontier Coding Model"
    context_window: 200000                 # hard context-fit filter
    max_input_tokens: 190000
    max_output_tokens: 64000
    pricing_tier: frontier                 # cost band, not exact $
    latency_tier: medium
    ability:
      coding: 10
      reasoning: 9
      writing: 8
    tool_support: [tool-use, file-edit, shell]
    vision_support: true
    ideal_use_cases: [coding, refactoring, agentic-tasks]
    avoid_use_cases: [bulk-cheap-classification]
    deprecation_status: active
    fallback: ["<strong-coding-model>", "<mid-tier-coding-model>"]
    source: manual
    last_updated: "2026-07-07"

  - provider: openrouter
    model_id: "<mid-tier-coding-model>"
    context_window: 128000
    max_output_tokens: 32000
    pricing_tier: low
    latency_tier: fast
    ability: { coding: 7, reasoning: 7, writing: 7 }
    tool_support: [tool-use, function-calling]
    vision_support: false
    ideal_use_cases: [coding, general]
    deprecation_status: active
```

---

## 5. How obsolescence is handled

- **New model ships** → append an entry to `models.yaml` (or let `providers
  refresh` write it). Instantly routable, no code change.
- **Model reprices** → change `pricing_tier`. Routing adapts automatically.
- **Model deprecated** → set `deprecation_status: deprecated` (penalized) or
  `retired` (excluded), and its `fallback` list steers routing to successors.
- **Provider renames ids** → `refresh_models` rewrites `model_id`; nothing
  downstream cares because logic reads fields, not names.
