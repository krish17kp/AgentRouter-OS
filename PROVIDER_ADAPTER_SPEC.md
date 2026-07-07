# AgentRouter OS — Provider Adapter Specification

> **Purpose:** Define the adapter contract that makes providers pluggable, and
> specify one adapter per supported provider. Adapters are the *only* place that
> knows provider-specific detail; they translate it into the neutral schema in
> [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md). This is how the system
> survives model/provider obsolescence: a new provider = a new adapter class; a
> provider change = one adapter edit.
>
> Scope tiers: **MVP → Capstone demo → Advanced → Production-future.**

---

## 1. The adapter contract

Every provider adapter implements the same interface. Method names are canonical
and match [ARCHITECTURE.md](ARCHITECTURE.md).

| Method | Signature (conceptual) | Responsibility | Tier |
|---|---|---|---|
| `list_models()` | → `list[ModelEntry]` | Return the models this adapter currently knows, already mapped to the registry schema. | MVP |
| `refresh_models()` | → `list[ModelEntry]` | Fetch the live model list from the provider and re-map to schema. Writes back to ModelRegistry. | Capstone demo |
| `map_capabilities(raw)` | `raw → ModelEntry` | Translate provider-native model metadata into schema fields (`ability`, `tool_support`, `context_window`, tiers, …). | MVP |
| `supports_execution()` | → `bool` | Whether this adapter can actually run a task. **Returns `False` for all adapters in v1.** | MVP |
| `execute(prompt, model)` | → result / raises | Run the recommended tool. **Raises `NotSupported` in v1** (planner-only boundary). | Production-future |

**Auth handling:** each adapter declares an `auth_model` (`none` \| `api-key` \|
`oauth` \| `local` \| `manual`). In v1, adapters that need credentials operate
in **catalog-only mode** — they can describe models (from static config or a
public list) but never call an authenticated endpoint. Live auth arrives with
`refresh_models` (Capstone, read-only key) and `execute` (Production-future).

**Common responsibilities (all adapters):**
- Never leak provider specifics beyond the adapter — output is always the
  neutral schema.
- Set `source: refresh` on entries produced by `refresh_models`, `manual`
  otherwise.
- Fail loud: a malformed provider response is surfaced, not silently dropped.
- Idempotent refresh: re-running `refresh_models` converges, doesn't duplicate.

---

## 2. Provider adapters

### 2.1 Claude Code adapter
- **Responsibilities:** map Claude Code's model catalog + tool capabilities
  (file-edit, shell, agentic tool-use) into the schema.
- **Required methods:** all five; `supports_execution` → `False` (v1).
- **Auth:** `oauth` / local CLI session. Catalog-only in v1.
- **Model refresh:** `refresh_models` reads the available model list from the
  local Claude Code environment/config.
- **Capability mapping:** high `tool_support` (file-edit, shell, tool-use);
  `vision_support` per model; coding-oriented `ideal_use_cases`.
- **Execution support:** planned strongest execution target (Production-future).
- **Limits:** requires a local Claude Code install for refresh.

### 2.2 OpenAI adapter
- **Responsibilities:** map OpenAI model list + function-calling/vision flags.
- **Required methods:** all five; `supports_execution` → `False` (v1).
- **Auth:** `api-key`. Catalog-only until a read key is provided (Capstone).
- **Model refresh:** `refresh_models` calls the models list endpoint, maps ids,
  context windows, and modality flags.
- **Capability mapping:** `tool_support` includes `function-calling`, `tool-use`;
  `vision_support` from modality metadata.
- **Execution support:** API-call execution (Production-future).
- **Limits:** ability scores (coding/reasoning/writing) are curated, not API-derived.

### 2.3 OpenRouter adapter
- **Responsibilities:** map OpenRouter's aggregated multi-vendor catalog —
  including per-model pricing, which maps cleanly to `pricing_tier`.
- **Required methods:** all five; `supports_execution` → `False` (v1).
- **Auth:** `api-key`.
- **Model refresh:** `refresh_models` pulls the full aggregated model list; the
  richest source for `providers refresh` breadth.
- **Capability mapping:** derive `pricing_tier`/`latency_tier` from OpenRouter
  metadata; `context_window` and modality from its model info.
- **Execution support:** unified API execution (Production-future).
- **Limits:** upstream metadata quality varies by underlying vendor.

### 2.4 Cursor adapter
- **Responsibilities:** map the models Cursor exposes for its IDE-based coding.
- **Required methods:** all five; `supports_execution` → `False` (v1).
- **Auth:** `oauth` / app session.
- **Model refresh:** `refresh_models` reads Cursor's configured model list where
  accessible; otherwise falls back to static config.
- **Capability mapping:** coding-heavy `ideal_use_cases`, `tool_support`
  includes `file-edit`.
- **Execution support:** hand-off style execution (Production-future); may be
  limited to prompt hand-off rather than programmatic run.
- **Limits:** less programmatic surface than API providers → may stay
  catalog + hand-off only.

### 2.5 Generic CLI-agent adapter
- **Responsibilities:** represent arbitrary local/CLI agents (e.g. a
  user-defined coding agent) described in config.
- **Required methods:** all five; `supports_execution` → `False` (v1), later
  gated by whether a run command is configured.
- **Auth:** `local` / `none`.
- **Model refresh:** `refresh_models` reads a user-provided config file listing
  the agent's models/capabilities (no network).
- **Capability mapping:** entirely config-driven.
- **Execution support:** shell-invoke the configured command (Production-future).
- **Limits:** only as accurate as the user's config; no auto-discovery.

### 2.6 Manual-agent adapter
- **Responsibilities:** the always-available fallback — a human, or any tool not
  otherwise modeled. Ensures `route` can always recommend *something*.
- **Required methods:** all five; `refresh_models` is a no-op returning static
  manual entries; `supports_execution` → `False` (always, by design).
- **Auth:** `manual`.
- **Model refresh:** none — entries are hand-authored placeholders.
- **Capability mapping:** generic, conservative scores; broad `tool_support`
  (a human can do anything, slowly) with `latency_tier: slow`.
- **Execution support:** never automated — always "do it yourself".
- **Limits:** intentionally low scores so it only wins when nothing else fits.

---

## 3. Adding a new provider

1. Add a provider entry to `registry/providers.yaml` (id, `adapter` type,
   `auth_model`, execution support).
2. Implement a class satisfying the contract in §1 (or reuse the generic
   CLI-agent adapter for config-only providers).
3. Ensure `map_capabilities` emits valid entries per
   [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md).
4. `providers refresh` picks it up automatically — no engine change.

## 4. What adapters must never do

- Hardcode a specific current model as special-case logic.
- Return provider-native shapes to the engine (always map to schema first).
- Auto-execute anything in v1 (`supports_execution` must be `False`).
- Swallow provider errors silently.
