# Architecture Decisions

## AD-1 — Route controls are a pre-filter, not an engine change
Filter flags (`--vendor`, `--host`, `--model`, `--max-price`, `--stable-only`,
`--available-only`) narrow the model list *before* `engine.route`. The engine's
eligibility/scoring stays untouched, so old behavior is preserved and controls are
unit-testable in isolation (`controls.apply_controls`). Dropped models surface in the
existing `excluded` list with a `control:` prefix — no new output shape.

## AD-2 — Preferences override weight shifts via a small engine hook
`--prefer-*` needs to win over the complexity/context weight shifts. Rather than
post-processing, `weights_for`/`route` take an optional `prefer` name; when set, a fixed
vector from `PREFERENCE_WEIGHTS` replaces the shift logic. Backward compatible (`prefer`
defaults to `None`). Vectors each sum to 1.0 (asserted by test).

## AD-3 — `--max-price` excludes unknown-price models (never fabricates)
Seed catalogs carry no per-token price yet. A price cap that silently kept unpriced
models would be misleading, so unpriced models are *excluded* under a cap with an
explicit reason. Consequence: `--max-price` currently drops all seeds; it becomes useful
once Phase P1 catalogs ingest real prices. Documented in KNOWN_LIMITATIONS.

## AD-4 — Confidence is rule-based and honest about a rule engine's certainty
The classifier is rule-based, so "confidence" is not a probability — it's a heuristic:
high when exactly one task-type family fires on a non-terse task, low on fallthrough to
`general`, on competing families, or on very short input. `route` abstains (flags
`needs_clarification`, suggests clarifying) rather than refusing — it still shows a
best-guess recommendation. Threshold is user-tunable (`--uncertainty-threshold`).
