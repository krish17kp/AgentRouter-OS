# Discover

Dispatched `repo-explorer` before writing any code. Findings that shaped scope:

- `agentrouter/engine.py:65-237` already implements deterministic task-complexity
  weighted scoring (`weights_for`, `score_models`, `eligibility`) with an
  explanation trail (`weight_shifts`, `excluded`) — this already satisfies the
  milestone's "task complexity signal" + "initial model-selection policy" +
  "explainable routing decision" asks. Not rebuilt.
- `agentrouter/hosts.py` (TASK-016) already implements verified execution-host
  states (`MISSING/INSTALLED/CONFIGURED/AUTHENTICATED/AUTHORIZED/DEGRADED`) for
  *dispatch-target* readiness, with `AUTHORIZED` deliberately never returned
  offline (command.md PHASE C, opt-in live check, not yet implemented anywhere
  — verified via `grep -rn AUTHORIZED` across `agentrouter/` and `tests/`, and
  `tests/test_host_states.py:231-244`'s explicit regression test that
  `detect_host()` never returns it).
- `agentrouter/refresh.py` already does dynamic model-catalog discovery from
  live provider HTTP APIs (OpenRouter, OpenAI) with provenance/source fields.
- `agentrouter/diagnostics.py` (TASK-018C) already implements the
  `Check(id, status, summary, remedy)` / `run_all()` pattern this milestone's
  "pre-flight" concept maps directly onto.
- `agentrouter/classifier.py:481-499` `_complexity()` is a deterministic
  regex/heuristic function, not an ML classifier — already matches the
  milestone's "conservative, testable heuristic is acceptable" guidance.
- `PROVIDER_ADAPTER_SPEC.md` stages authenticated calls: catalog-only in v1, a
  read-only key at `refresh_models` (Capstone), `execute` (Production-future).
  A live quota/usage check is a *third* kind of authenticated call the spec
  doesn't define yet.
- `loop/BACKLOG.yaml` P2: "live host access verification, needs: opt-in
  network + credentials" is `blocked_external` — this project's own state
  tracking already treats live provider verification as credential-gated, not
  a code gap.
- `agentrouter/controls.py:122` `--available-only` is the real precedent for
  "drop a model whose readiness fact is unfavorable" — single pass, no
  re-rank, offline.

Real gaps identified (nothing existing covered these):
1. Introspective harness detection — "what tool is running *this* agentrouter
   process" (distinct from `hosts.py`'s prospective "can we dispatch to X").
2. A usage/quota state model distinct from host readiness
   (available/exhausted/unknown/unsupported), honestly UNSUPPORTED for every
   real provider today since no adapter has a verified live endpoint.

Session env evidence (not guessed): this session's own process has
`CLAUDECODE` set (confirmed via `env | grep -i claude`), which is the only
first-hand-verified harness signal available; `integrations/README.md`
confirms Codex/Cursor/Antigravity integration is pure pasted-instructions with
zero runtime footprint in this repo — so no env-var evidence exists for them,
and none was fabricated.
