# Codex Handoff - AgentRouter OS

Last updated: 2026-07-31 (iter 20 — RC mutation gate CLOSED; branch hygiene done; TASK-011 kickoff)

## Current state (iter 20)

- **Branch topology (authoritative):**
  - `main` — stable, untouched. Never merge into it without explicit owner approval.
  - `release/agentrouter-v0.5-rc1` — integration branch @ `fa0a203`. **NOT RELEASE READY**
    (context_band held-out 0.6667 < 0.90). Mutation gate now **PASSES**.
  - `task/TASK-011-context-band-data` — to be branched from RC for TASK-011; all TASK-011
    commits/pushes land here; draft PR targets the RC.
  - `mutation-kill-safety` — **DELETED** (local + remote). PR #1 **CLOSED** as fully superseded
    by `tests/test_mutation_kills.py` (its five files were self-described mutation-hardening for
    modules the RC already covers at 0.985; RC campaign passes without them).
- **Mutation (TASK-010b CLOSED):** full Linux campaign (mutmut 3.6.0, 923 mutants) overall
  **0.9837**; `safety_policy_execution` **0.985** (>=0.95); `routing_engine` **0.9815** (>=0.85);
  completeness + all-reviewed gates green; 15 allowlisted-equivalent survivors; no safety/auth/
  policy/execution-bypass survivor. Extracted `cli.execute()` gate logic into undecorated
  `_execute()` so mutmut can instrument it. Local iteration via Docker container `armut`.
- **CI on `fa0a203`:** Critical Mutation Testing GREEN, Security GREEN, test matrix 3.10-3.13 +
  test-windows + build-smoke GREEN; only `release-gate` RED (honest context-band gate).
- **Next:** TASK-011 context-band data/annotation/adjudication/training/eval program on
  `task/TASK-011-context-band-data`. Do NOT reuse or tune against the frozen holdout; the 0.90
  gate is unchanged; RC stays NOT RELEASE READY.

---

## Historical takeover notes (iter 18-19)

## Repository and Git state

- Path: `D:\Krish\Agentrouteros`
- Remote verified: `origin https://github.com/krish17kp/AgentRouter-OS.git`
- Initial branch: `main` tracking `origin/main`
- Initial HEAD: `602321af91ff298c0d5b59d6d36c24f845557fc1`
- Target authorized branch: `release/agentrouter-v0.5-rc1` (not yet created at this checkpoint)
- `git diff --check` and `git diff --cached --check`: no integrity errors at takeover.

### Inherited index (must not be discarded)

Nine staged renames move packaged evaluation data into the Python package:

- `benchmarks/{classifier_gold_v1,routing_gold_v1}.yaml` -> `agentrouter/benchmarks/`
- Seven `evaluation/fixtures/*.jsonl` files -> `agentrouter/evaluation/fixtures/`

### Inherited unstaged tracked work (must not be discarded)

`.github/workflows/release.yml`, `.gitignore`, `CHANGELOG.md`, `KNOWN_LIMITATIONS.md`,
`LOOP_LOG.md`, `LOOP_STATE.json`, `README.md`, `RELEASE.md`, `TESTING.md`,
`agentrouter/{__init__,classifier,cli,hosts}.py`, evaluation base and seven adapters,
`agentrouter/server/{__init__,app,service}.py`, evaluation report artifacts, `examples/README.md`,
`pyproject.toml`, and three focused tests. Initial unstaged diff: 36 files, 951 insertions and
1,701 deletions (the deletions are primarily regenerated evaluation output).

### Inherited untracked work (must not be discarded)

`.claude/` control-plane reference files; `PRODUCTION_READINESS.md`, `QUALITY_DASHBOARD.md`,
`UPGRADING.md`; `agentrouter/{mcp_server,observability}.py` and
`agentrouter/server/limits.py`; the complete `loop/` control plane and TASK-001..007 evidence;
`sdk/typescript/`; and tests for context bands, MCP, observability, properties, and server limits.
`.mutmut-cache` is untracked generated state and must not be committed.

### Ignored/local state (exclude from commits)

`.env` (contents not read or printed), `.venv/`, `.coverage`, `.hypothesis/`, `.pytest_cache/`,
`.ruff_cache/`, Python caches, `agentrouter_os.egg-info/`, `artifacts/evaluation/current/`, `build/`,
`dist/`, `data/`, and `sdk/typescript/node_modules/`.

## Reconstructed state

Inherited work implements exact model/host routing, route controls, confidence/abstention, tool
taxonomy, plugin installers, setup, structured private-by-default logging and optional OTel,
request IDs, bounded rate limiting/idempotency, local FastAPI/Python SDK, safe MCP read/route tools,
TypeScript SDK, evaluation framework, packaged eval resources, SBOM/provenance release changes,
and prior audit repairs. These remain under independent verification.

Locally actionable work remains, despite stale `BLOCKED_EXTERNAL` flags:

1. TASK-008 safe empty plugin-directory cleanup with path/symlink/user-file protections.
2. TASK-009 genuinely held-out context-band generalization evaluation and leakage detection.
3. Bounded Linux mutation-testing GitHub Actions workflow and a real CI score.
4. Fix baseline formatting drift in three `.claude/hooks` files and any later audit/CI findings.

External/owner-controlled items remain live provider credentials/catalogs, paid model benchmarks,
hosted/team infrastructure, marketplace/PyPI publication, real beta users, production deployment,
and final irreversible product decisions.

## Independently reproduced takeover baseline

- Python: `427 passed` (one Starlette/httpx deprecation warning), 2026-07-20.
- Claude hook/control tests: `15 passed`.
- Ruff lint: clean.
- Ruff format: **FAIL**, would reformat `.claude/hooks/post_edit_check.py`,
  `pre_tool_guard.py`, and `test_hooks.py`.
- Bandit: zero findings; five justified nosec exclusions.
- pip-audit: no known vulnerabilities in `requirements.txt`.
- Evaluation: `98.32/100`, 165 cases, all seven current gates pass.
- TypeScript SDK: `npm ci`, 8/8 tests, typecheck clean.
- Packaging: wheel and sdist build successfully; setuptools emits future license-metadata warnings.
- Clean wheel: fresh Python 3.13 venv, installed wheel with `[server,mcp]`, non-repository cwd;
  import/version, help, init, setup, registry list, hosts list, route, eval list-datasets,
  `eval run --all`, packaged benchmarks/fixtures/plugins, API import, and MCP import all pass.
- Clean-wheel temp evidence path:
  `C:\Users\krish\AppData\Local\Temp\agentrouter-codex-wheel-984c6723ae73494984c5575dd3533ae6`.

## Current next command/task

Iter 19 done (Claude, 2026-07-31 — decision A): built a dev-only LEARNED context-band classifier
(`agentrouter/context_model.py`, multinomial LR, pure-Python runtime, packaged JSON weights) and
evaluated rules / learned / hybrid against the frozen holdout ONCE. **Proven ceiling** — none
reach 0.90: rules 0.6667 (macro-F1 0.6792), learned 0.6889 (macro-F1 0.6613, collapses medium
recall), hybrid 0.6444. Learned is not significantly better than rules and has a lower macro-F1,
so shipped **rules-active** (`_USE_LEARNED_BAND=False`); learned kept as a tested, flag-gated
artifact with rule fallback. Study: `loop/tasks/TASK-009-context-band-holdout/learned-model-study.md`.
Baseline: 481 collected — **480 passed** / 1 env-skip (otel), ruff/format clean, bandit 0, eval
**98.23** Release-ready NO (context_band gate). Graphify post-impl 2309 nodes / 4319 edges,
`context_model.py` leaf, no cycle. Clean-wheel verified (model JSON packaged, loads from fresh
install). Independent gates: release-auditor FAIL-to-release / correctly HELD (all claims
reproduced); security-reviewer no CRITICAL/HIGH, one LOW fixed (`load_model()` TypeError catch).
One plugin backup test is order-flaky on Windows (passes isolated), unrelated to TASK-009.

Iter 18/18b (2026-07-20): TASK-008 re-audited PASS (no repair); TASK-010 locally validated (CI
score pending push); bandit regression fixed; Graphify activated; autonomy codified.

Remaining is owner/external-blocked:
- context_band held-out gate (0.6667 < 0.90) — **PROVEN DATASET CEILING** (rules/learned/hybrid all
  tested). Closing honestly needs a larger human-labeled dev set or real-file context signals, OR an
  owner decision to adjust/justify the gate. Do NOT tune against the frozen holdout.
- release/agentrouter-v0.5-rc1 push — GATED: owner authorization required to push an RC while a
  mandatory gate fails.
- Phases B-J (live catalogs, paid benchmarks, hosted infra, PyPI/marketplace, beta) — external/owner.

Resume/re-verify with:

```console
git status --short --branch
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m agentrouter eval run --all
graphify update .
```

