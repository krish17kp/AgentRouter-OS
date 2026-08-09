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

## AD-5 — The API contract is a committed artifact, not the live `/openapi.json`
`GET /openapi.json` reflects whatever the process serves, so it can never detect its
own regression. The contract is instead exported to `contracts/http/v1/openapi.json`
and committed; CI regenerates it from the real app and diffs *semantically*, not
textually, because a textual diff cannot tell a reordered key from a removed field.
Three consequences follow.

**The export must be byte-stable or the diff is noise.** Keys are recursively sorted,
order-insensitive lists (`required`, `enum`, `tags`) are normalised, and trivial
`servers` entries are dropped — but a non-trivial `servers` is kept, since relocating
the API breaks every client URL. Provenance (commit, timestamp, tool version) lives in
`manifest.json`, never in the contract: putting it in the contract would make every
regeneration a diff and destroy the signal.

**Endpoints must be typed or the gate guards nothing.** Four operations were declared
`-> dict`, so the contract said only "an object" for their responses and a renamed
field produced no diff at all. They now use response models that declare the stable
top-level keys with `extra="allow"`, which makes the fields visible to the checker
without stripping anything from the wire. For the same reason authentication is a
declared `APIKeyHeader` security scheme rather than a bare `Header` parameter — as a
parameter it was indistinguishable from any other optional header, so adding or
removing auth on an endpoint was invisible.

**A gate you can edit is not a gate.** The baseline is refused outright if it contains
an unresolvable, self-referential or remote `$ref`, because such a ref inlines as `{}`
and would make the whole schema look permissive — a one-character edit could turn the
build green. Ref expansion is bounded, and validation memoises resolved refs so a
document with fan-out references cannot hang CI. Export refuses to follow a symlink or
write outside the repo root. Accepting a breaking change requires an explicit reason,
appends to a history a later export cannot erase, and records only the changes the
checker itself found — so the audit trail cannot assert a break that never happened.
