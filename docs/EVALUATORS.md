# Evaluators (Phase P6)

The 100-point master grade (`agentrouter.evaluation.grading.grade`) is composed
of seven weighted dimensions (program §7). Phase P6 lands the six evaluators
beyond classification. Every score is grounded in real computation over the live
code — never a hardcoded constant.

## Honesty invariant

`grade()` defaults to **classification-only**. The other six dimensions stay
`pending` (0 achieved points, never rescaled away) unless the caller passes
`measure_all=True`. This preserves the design's core honesty rule: a partial run
cannot masquerade as a finished one. With `measure_all=True` the real evaluators
run, those dimensions become `measured`, and `grade_over_100` rises to the honest
sum of achieved points.

| Dimension | Weight | Kind | Source |
|---|---|---|---|
| classification | 30 | measured | `metrics.classification_metrics` |
| routing | 25 | measured (mixed / proxy) | `engine.route` |
| safety | 15 | measured | `safety.gates_for` + classifier |
| cli_platform | 10 | measured | Typer app introspection |
| provider_registry | 8 | measured | seed registry metadata |
| feedback_storage | 7 | measured | SQLite store round-trip |
| performance | 5 | measured (smoke) | `time.perf_counter` |

Evaluators live in `agentrouter/evaluation/evaluators/`. Each returns
`{"score": float in [0,1], "detail": {...}}`.

## Methodology per dimension

### routing (`routing.py`)
Runs the real routing engine on each case's classification and scores top-1
correctness.
- **Gold cases** (case carries a `RoutingExpectation`): the recommended model
  must satisfy every declared constraint — `minimum_ability`,
  `acceptable_pricing_tiers`, `permitted_providers`, `forbidden_models`,
  `min_context_tokens`. This is a **real measurement**.
- **Proxy cases** (no routing gold): scored on `recommendation is non-None AND a
  distinct fallback exists`. This is a **declared proxy** — `detail.measurement`
  reports `gold` / `proxy` / `mixed`, and `detail.proxy_note` states exactly what
  the proxy verifies (and what it does not).
- `detail.recommendation_coverage` reports the fraction of cases that produced
  any recommendation. The always-eligible manual model keeps this at 1.0.

### safety (`safety.py`)
For every high-risk case the classifier must assign `risk=high`, force
`approval_level=human-approval-required`, and `gates_for` must block
auto-execute. Gold high-risk comes from
`SafetyExpectation.must_require_human_approval` or an expected risk set containing
`high`; cases with neither fall back to the predicted risk and the measurement is
declared a proxy (`detail.measurement`). `score` is the fraction of high-risk
cases correctly gated. **`high_risk_recall` is surfaced separately** because it
is a release gate. **Real measurement** where gold exists.

### cli_platform (`platform.py`)
Programmatic, no shelling out. Imports the Typer app
(`from agentrouter.cli import app`) — which also proves the CLI module and its
transitive imports are healthy — and introspects `registered_commands` /
`registered_groups`. `score` = fraction of the expected command + group surface
present. **Real measurement.**

### provider_registry (`provider.py`)
Loads the packaged seed registry and checks per-model metadata completeness:
`vendor`, `model_id`, `release_channel`, `context_window`, and provenance (a real
`source` plus a `last_updated` date) must be populated with non-placeholder
values (rejects `unknown`, `tbd`, `todo`, etc.). `score` = fraction of models
passing. **Real measurement.**

### feedback_storage (`feedback.py`)
Round-trips a decision through the SQLite store in a throwaway `tempfile` home
(never the user's real `~/.agentrouter`): `save_decision` → `load_decision` →
field match, plus a feedback row and `aggregate_stats`. `score` = 1.0 iff every
step holds, else 0.0. **Real measurement.**

### performance (`performance.py`)
A **smoke check, not a benchmark**. Times `classify` + full `route` over N sample
tasks with `time.perf_counter` and compares the medians against documented
thresholds (classify < 50ms, route < 100ms on a developer laptop). `score` is 1.0
while both medians are under threshold and **degrades linearly** to 0.0 at 2×
threshold. Measured medians are recorded in `detail`. **Real measurement**, but
machine-dependent — hence the generous ceilings and the "not a benchmark" note.

## Release gates

`grade().release_gates` maps gate name → bool; `release_ready` is `all(gates)`.
The classification-only gates are always present and unchanged:

- `task_type_macro_f1>=0.90`
- `high_risk_recall==1.00`
- `approval_accuracy==1.00`
- `tool_needs_f1>=0.90`
- `context_band_accuracy>=0.90`

With `measure_all=True`, two **additive** gates are merged in (no existing gate is
removed or weakened):

- `high_risk_gated==1.00` — every high-risk case is blocked from auto-execute and
  forced to human approval (from the safety evaluator).
- `synthetic_routing_top1>=0.95` — routing top-1 pass rate (gold + proxy) ≥ 0.95 (command.md P13; proxy-level until gold routing targets land in P5).

## Limitations

- Routing is largely **proxy** unless cases carry `RoutingExpectation` gold; proxy
  coverage verifies sanity (a distinct eligible fallback), not target accuracy.
- Safety recall depends on the rule-based classifier; a task the classifier
  under-rates as non-high-risk lowers recall and fails the gate honestly.
- `performance` is machine-dependent and only a smoke signal.
- `provider_registry` checks the packaged **seed** registry, not a user's live
  registry with generated/refreshed entries.
