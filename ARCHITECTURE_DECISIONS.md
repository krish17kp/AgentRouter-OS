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
build green. A baseline that exists but cannot be *parsed* is likewise refused rather
than treated as absent: collapsing "missing" into "unreadable" would let corrupting the
file bypass the same refusal that deleting it is meant to trigger. Ref expansion is
bounded by one budget for the whole comparison (a per-call budget bounded nothing, since
the traversal re-enters it for every property), validation memoises resolved refs so a
fan-out document cannot hang CI, and the comparison has its own depth ceiling
independent of `$ref`. Export refuses to follow a symlink *or a hardlink* — a hardlink
is invisible to `is_symlink()` and resolves inside the root — and refuses to write
outside that root.

Accepting a breaking change requires an explicit reason and records only changes the
checker itself found, so the trail cannot assert a break that never happened. But the
honest limit is this: **`contracts/` is a committed text file, and code review is what
protects it.** A routine `contract export` will not erase the history; an editor will.
The control that does not depend on good behaviour is in CI, which compares the live app
against the contract on the **base branch** — a file the author of the pull request does
not control. That, not `validate_refs`, is what catches a doctored or deleted baseline.

**`contracts/http/v1/` versions the artifact, not the API.** There is one app and one
exported document, covering every path served — including the unversioned `/health` and
`/ready`. A `contracts/http/v2/` directory would not bring a `/v2` API into existence;
it would describe the same app twice and orphan the v1 baseline at the exact moment v1
most needs protecting. A genuinely incompatible API is versioned in the URL space
(`/v2/...` alongside `/v1/...`, both in the one contract, with `endpoint_removed`
guarding the old paths), and this directory stays as it is.


## AD-6 — `required` is read per direction, and engine-owned payloads stay untyped
Two classification rules in the compatibility checker look asymmetric and are deliberately
so.

`required` means opposite things on each side of a call. On a request it is an obligation
on the caller, so making a field required breaks them and dropping the obligation is
additive. On a response it is a guarantee from the server, so *adding* a required field is
a stronger promise (additive) and removing one withdraws a guarantee (breaking). Reading
it symmetrically had a concrete cost: FastAPI marks every non-defaulted response field
required, so adding a field to `ModelSummary` — the most likely future change to this API,
and unambiguously safe for clients — failed CI and forced `--accept-breaking`. A gate that
cries wolf gets routed around, and then it protects nothing.

The response envelopes declare the engine-owned payloads as `Any` rather than `dict` or
`list`. `/v1/decisions/{id}` replays a blob persisted by whatever engine version wrote the
row; the store keeps opaque JSON with no schema version. Asserting today's shape over
yesterday's data turns a working `200` into a `500` the first time any historical row
drifts — a regression on data the user already has, which is the one failure a
*compatibility* change must not introduce. The field **names** are what the checker
protects, and a rename or removal is still detected.

An earlier draft of this note justified the choice by claiming the checker only compares
the `anyOf[T, null]` union and never its interior. That was true when it was written and
is false now — `_unwrap` was added precisely so the interior *is* compared. The reason
stands on its own without that crutch: these values are replayed, not produced, so a type
here is a promise about data we did not write and cannot migrate. The rule admits no
exceptions, because the first pass left `prompt` as `str | None` and a decision persisted
when `prompt` was a dict returned 500.

## AD-7 — Approved Rust-native target, phased behind the existing contracts
The owner has approved a Rust-native implementation as the long-term target, reviewed
externally against the foundation-document inventory (`AGENTROUTER_FOUNDATION_REVIEW.md`).
The **current Python implementation remains the shipping system and the sole release-gate
authority** until the migration completes; this decision changes the target, not today's
behavior, test requirements, or release gates.

The migration is phased module-by-module (order, acceptance tests, and rollback criteria
in [RUST_MIGRATION_PLAN.md](RUST_MIGRATION_PLAN.md)), because the alternative — a single
rewrite-and-cutover — would make every one of this document's prior decisions (the
committed contract artifact in AD-5, the request/response `required` asymmetry in AD-6,
the price-cap honesty in AD-3) re-provable only in aggregate, with no way to isolate which
ported component caused a regression. Each existing compatibility mechanism —
`contracts/http/v1/` + the `api-compatibility` CI job, `CLI_SPEC.md`'s documented-command
tests, the registry YAML schema, the SQLite decision-log format, the seven evaluation
gates — is reused as the acceptance bar for its Rust replacement rather than redesigned,
so a ported module either reproduces the existing committed contract or it is not done.

Consequences: no Python module is deleted until the full migration is complete and has run
a full release cycle in production (see Rollback in the migration plan); no release,
coverage, or mutation threshold is lowered to accommodate different Rust tooling
(`cargo-mutants`/`cargo-audit` replace `mutmut`/`bandit` only once independently
re-validated at the same thresholds); and the frozen-holdout annotation policy (no AI
annotates or adjudicates) carries over unchanged, since it is a human-process requirement,
not an implementation detail.

**Revision (2026-10-13):** an independent architectural review found the scope this
decision originally pointed at — the first cut of `RUST_MIGRATION_PLAN.md` — too shallow
in three ways, since corrected in that document rather than here (this entry stays a
pointer, not a restatement). First, `agentrouter/annotation/*` was marked "stays Python
indefinitely"; the owner has since clarified it is in scope for eventual migration too,
*without* changing the human-review requirement, the frozen-holdout leakage guardrail, or
pack-blinding behavior — those are carried over as acceptance criteria, not relaxed.
Second, the module inventory was built from assumption rather than a recursive read of
`agentrouter/`; the plan now carries a real subsystem inventory with IMPLEMENTED/PARTIAL/
INTERFACE ONLY/PLANNED/MISSING/BLOCKED status per area, which surfaced that real
agent-execution adapters and multi-agent orchestration do not exist in Python today — they
are net-new design work, not port targets, and are scoped as such (milestones R6/R7).
Third, the crate-boundary sketch and milestone list were underspecified; both are now
concrete in the plan. None of this changes what this decision already said: Python remains
the sole shipping/release-gate authority, no code was deleted, and no threshold moved.
