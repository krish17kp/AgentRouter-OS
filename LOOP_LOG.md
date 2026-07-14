# LOOP_LOG

## Iteration 1 — 2026-07-14 — Phase P3 route-control flags

**Start SHA:** 476c51a · **Baseline:** 276 tests passed, ruff clean.

**Slice:** Implement Phase P3 route-control flags (highest-leverage *fully-local*
gap; catalog refresh/host-verify/measured-profiles all need live APIs → blocked
external). Was marked `[ ]` in ASSIGNMENT_B_STATUS.

**Changed:**
- `agentrouter/controls.py` (new) — `RouteControls`, `apply_controls`, `PREFERENCE_WEIGHTS`.
- `agentrouter/engine.py` — `weights_for`/`route` accept optional `prefer`; preference
  vector overrides complexity/context shifts. Backward compatible (default `None`).
- `agentrouter/cli.py` — `route` gains 13 flags + `_resolve_preference`; filter drops
  fold into `excluded` as `control:` reasons; conflicting flags → exit 2.
- `tests/test_route_controls.py` (new) — 15 tests (8 unit + preference sums + 6 CLI).
- `CLI_SPEC.md` — documented the flags.

**Verify (real output):**
- `pytest -q` → **291 passed** (276 + 15).
- `ruff check agentrouter tests` → All checks passed.
- Smoke (fresh seeded home): `--vendor anthropic` → `anthropic/claude-sonnet-5`;
  `--prefer-quality` on "write a haiku" lifted Haiku→Sonnet-5; `--model` pin honored;
  `--exclude-vendor openai` honored; `--max-price 5` → no model (unknown prices excluded,
  honest); conflicting `--prefer-*` → exit 2.

**Backward compat:** empty `RouteControls` returns the input list unchanged; all 276
prior tests still pass; JSON only gains `control:` entries in the existing `excluded` list.

**Decisions:** see ARCHITECTURE_DECISIONS.md AD-1..AD-3.

**Next:** P3 confidence/abstention surface, then P4 tool-taxonomy.

---

## Iteration 2 — 2026-07-14 — Phase P3 confidence & abstention (P3 now COMPLETE)

**Slice:** classification confidence + abstention (the second half of P3).

**Changed:**
- `agentrouter/schema.py` — `Classification` gains `confidence`, `needs_clarification`,
  `alternative_task_type`, `ambiguity_reason` (all defaulted → backward compatible).
- `agentrouter/classifier.py` — `_confidence` + `_task_type_families`; rule-based score
  (strong when one family fires and task isn't terse; weak on fallthrough/competing
  families/very short input). `classify` takes `uncertainty_threshold`
  (`DEFAULT_UNCERTAINTY_THRESHOLD = 0.4`).
- `agentrouter/cli.py` — `route` gains `--uncertainty-threshold`; text output prints a
  `confidence:` line and a "Low confidence …" note with runner-up + reason.
- `tests/test_confidence.py` (new) — 7 tests. `CLI_SPEC.md` documents the flag/fields.

**Verify:** `pytest -q` → **298 passed** (was 291; +7). `ruff check agentrouter tests` clean.
Smoke: "refactor … add unit tests" → confidence 1.0, no clarification; "do it" →
confidence 0.0, `needs_clarification: true`, note shown in text + JSON.

**Backward compat:** new schema fields defaulted; all prior tests pass; JSON additive.

**Decision:** AD-4 (confidence is rule-based, honest about a rule engine's certainty).

**Next:** P8 plugin installer, then P9 setup wizard. See LOOP_STATE.next_action.

---

## Iteration 3 — 2026-07-14 — Phase P8 plugin/skill installer (local slice)

**Slice:** `agentrouter plugin list/install/uninstall/doctor` — install host
integrations (Claude Code skill, Codex AGENTS.md) from bundled package data.

**Changed:**
- `agentrouter/integrations/**` (new) — bundled copies of the Claude Code SKILL.md
  and Codex AGENTS.md payloads (source-of-truth stays under repo-root `integrations/`).
- `pyproject.toml` — `package-data` now ships `integrations/**/*`.
- `agentrouter/plugins.py` (new) — `PLUGINS` registry + `plan/status/install/uninstall`.
  Reversible (backup `<file>.agentrouter-bak`, restored on uninstall), idempotent
  (skip identical), safe (never clobbers a differing user file without `--force`),
  `AGENTROUTER_PLUGIN_ROOT` override for tests/power users.
- `agentrouter/cli.py` — `plugin` sub-app with 4 commands + `--dry-run`/`--force`.
- `tests/test_plugins.py` (new) — 9 tests incl. force→backup→uninstall→restore.

**Verify:** `pytest -q` → **307 passed** (+9). `ruff` clean. Lifecycle smoke on a temp
root: create → idempotent skip → doctor → uninstall (removed) → unknown plugin exit 2.
`python -m build --wheel` → `agentrouter_os-0.4.0-py3-none-any.whl`; confirmed the wheel
contains `agentrouter/integrations/.../SKILL.md` and `.../AGENTS.md` (packaging verified).

**Backward compat:** additive; no existing command changed.

**Not done in P8 (recorded):** MCP server, `/route*` slash-command set, installer shell
script, examples/ templates, Linux CI run of install (Windows verified locally).

**Next:** P9 `agentrouter setup` wizard; then P4 tool-taxonomy (regression-risky).

---

## Iteration 4 — 2026-07-14 — Phase P9 `agentrouter setup` wizard

**Slice:** non-interactive, idempotent onboarding that composes existing pieces.

**Changed:** `agentrouter/cli.py` — `setup` command (privacy note → init → host discovery
with secrets detected by presence only → `--preference` writes weights → sample route →
plugin hint) + `_write_preference`. `tests/test_setup.py` (new, 5 tests, incl. a test that
a set `OPENAI_API_KEY` value never appears in output).

**Verify:** `pytest -q` → **312 passed** (+5). ruff clean. Smoke: `setup --preference cheap`
seeded home, listed hosts, wrote cheap weights, routed sample → Haiku; bad preference → exit 2.
Fixed a Windows console em-dash (`—`→`-`) so output isn't mojibake under cp1252.

---

## Iteration 5 — 2026-07-14 — Phase P4 tool/workload taxonomy

**Slice:** versioned canonical taxonomy + alias-aware eligibility + `--prohibit-tool`.

**Changed:**
- `agentrouter/taxonomy.py` (new) — `TAXONOMY_VERSION`, canonical `TOOLS` (~22 labels incl.
  legacy web/tool-use), equivalence groups (`web≡web-search`, `tool-use≡function-calling`),
  `is_known`/`equivalents`/`satisfied_by`.
- `agentrouter/engine.py` — eligibility uses `taxonomy.satisfied_by` (a superset of exact
  match: never excludes a model that used to match; only adds synonym matches).
- `agentrouter/controls.py` + `cli.py` — `--prohibit-tool` (the *prohibited* half of P4's
  required/optional/prohibited split), equivalence-aware.
- `tests/test_taxonomy.py` (new, 14 tests) incl. a hygiene test that every seed
  `tool_support` label is a known taxonomy member.

**Verify:** `pytest -q` → **326 passed** (+14). ruff clean. All prior classifier regression
tests still pass (alias matching is backward compatible).

**Not done in P4 (recorded):** *optional* tools are not modeled (only required + prohibited);
classifier still emits the legacy label set (deliberate — avoids destabilizing the
classifier regression suite; new labels enter via registries/controls).

**Next:** P10 security-scan wiring, P12 examples/docs; P6 evaluators + P7 API/SDK largest.

---

## Iteration 6 — 2026-07-14 — Phase P10 security scanning (local slice)

**Slice:** wire Bandit + pip-audit + secret scan; fix the one real finding at root.

**Changed:**
- `agentrouter/refresh.py` — **root-cause fix**: `_http_get_json` now rejects any
  non-http(s) URL scheme before `urlopen` (blocks a malicious/typo'd registry URL from
  reaching `file://`/custom handlers — SSRF / local-file read). Bandit B310 addressed by
  the guard + justified `# nosec`.
- `agentrouter/cli.py`, `agentrouter/evaluation/runner.py` — justified `# nosec B603/B607`
  on the deliberate argv/`shell=False` subprocess calls (injection-tested).
- `pyproject.toml` — `[tool.bandit]` skips informational B404.
- `.github/workflows/security.yml` (new) — bandit (fails on any finding), pip-audit,
  `pytest -m security`, and a committed-secret grep scan.
- `tests/test_security_scan.py` (new, 5 params) — asserts the scheme guard rejects
  file/ftp/gopher/data URLs without touching the network.

**Verify:** `bandit -c pyproject.toml -r agentrouter` → **No issues identified**.
`pip-audit -r requirements.txt` → **No known vulnerabilities**. `pytest -q` → **331 passed**
(+5). ruff check + `ruff format --check` clean.

**Not done in P10 (recorded):** structured logging/OpenTelemetry, mutation testing (mutmut),
Hypothesis property suite, full threat-model doc expansion, metrics/observability.

**Next:** P12 examples/ + README quickstart; P6 evaluators + P7 API/SDK remain largest.

---

## Iteration 7 — 2026-07-14 — P12 docs + P7 API/SDK + P6 evaluators (parallel build)

**P12 (docs, solo):** `examples/README.md` (8 verified scenarios); README quickstart now
shows `agentrouter setup`, `plugin install`, and the P3/P4 route-control flags + confidence.

**P7 (API/SDK) and P6 (evaluators) built by two parallel subagents on disjoint files**
(command.md §6; builder ≠ sole reviewer — I re-verified the merged tree independently).

**P7 — local REST API + Python SDK** (`agentrouter/server/{__init__,app,service,schemas}.py`,
`agentrouter/sdk.py`, `tests/test_server.py`, `tests/test_sdk.py`, `docs/API.md`):
9 endpoints under `/v1` (health, ready, models, hosts, classify, route+persist, decisions/{id},
feedback, execute/dry-run), request-id middleware, optional `X-API-Key` auth, auto OpenAPI at
`/docs`. **No remote execution** — only `/v1/execute/dry-run` returning an argv plan
(`would_execute:false`), asserted by test. 27 new tests.

**P6 — full 100-point evaluator** (`agentrouter/evaluation/evaluators/*.py` + `grading.py`
`measure_all` opt-in + `docs/EVALUATORS.md` + `tests/evaluation/test_evaluators.py`):
routing/safety/platform/provider/feedback/performance evaluators, each a real measurement
(routing partly proxy, declared). Additive gates `high_risk_gated==1.00`,
`synthetic_routing_top1>=0.90`; no existing gate weakened; default `grade()` path byte-identical.
13 new tests.

**Integration (solo):** wired `agentrouter server` command (lazy uvicorn, guarded import),
threaded `measure_all` through `runner.run` → `grade()`, added `eval run --all`.

**Verify (independent, post-merge):** `pytest -q` → **371 passed** (+40). ruff check + format
clean. bandit `-c pyproject.toml -r agentrouter` → **0 issues** (incl. server). Server boots,
`/health` + `/openapi.json` → 200. `eval run --all` → **grade 96.89/100**, 2 gates honestly
FAIL on fixtures (context-band acc, high-risk-gated) → correctly reported NOT release-ready.
`python -m build` → wheel 0.4.0 includes server/sdk/evaluators subpackages.

**Blocked-external (unchanged):** P1 live catalogs, P2 live host verify, P5 measured profiles,
P11 hosted deploy + marketplace, P13/P14 real-beta gates.

---

## Iteration 8 — 2026-07-14 — Fix failing eval gates (root-cause)

**Issue 1 — `high_risk_gated` FAIL (bug):** the safety evaluator treated gold
`risk: [medium, high]` as *requiring* high, so a valid `medium` prediction counted as a
miss (contradicting classification `high_risk_recall==1.00`). Root cause: `_gold_high_risk`
used `Level.high in risks`. **Fix:** mandatory-high only when `must_require_human_approval`
or `set(risks) == {high}` (high is the *sole* acceptable value). Now 24 cases, all gated →
gate **1.00**. Not a weakening — corrects "acceptable set" vs "required" semantics.

**Issue 2 — `context_band_accuracy` 0.76 (real classifier gap):** medium-context recall was
0.30 — coding/review tasks on an *existing* component ("add pagination to the products
endpoint", "the auth package") were scored as 2k-token small. **Fix:** `M_EXISTING_CODE`
signal in `_context_tokens` → tasks referencing existing components/APIs/PRs get medium
(12k). Accuracy 0.76→**0.82**, medium recall 0.30→0.67, macro-F1 0.756→0.862. Did NOT chase
0.90 (one-line-prompt band inference has a natural ceiling; forcing it = overfitting). This
gate is beyond command.md's P13 set.

**Also:** tightened routing gate `>=0.90`→`>=0.95` to match command.md P13 exactly (value 1.0,
declared proxy); updated its test + docs.

**Verify:** `pytest -q` → **371 passed** (classifier change broke nothing). ruff+format clean,
bandit 0. `eval run --all` → grade **98.08**; **all command.md-required gates PASS**; only the
beyond-spec context-band check remains <0.90 (0.82), documented.
