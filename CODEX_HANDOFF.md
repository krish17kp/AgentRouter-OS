# Codex Handoff - AgentRouter OS

## Storage relocation — 2026-11-15

Active release checkout: `/data/AgentRouter-production` on branch
`release/agentrouter-v0.5-rc1` at pushed head `82babba`. The prior checkout is detached and
preserved at `/home/krish/.codex/worktrees/agentrouter-production/AgentRouter-OS`.
Tracked code/test diffs were verified identical before transfer; untracked TASK-153,
154, and 155 task notes and `/data/agentrouter-recovery/task154.patch` were copied.
Context documents are at `/data/agentrouter-context`. Shared Git metadata and Python
venv remain at `/data/AgentRouter-OS`. New Rust build output points to
`/data/agentrouter-build/target`; source `/data/agentrouter-build/environment.sh`
for that location and `/data/agentrouter-build/tmp` temporary files.

The Python TASK-153 full regression in the previous checkout completed: 2,597 passed,
7 skipped, 1 warning, 501.42s; coverage is 92.004% statement, 87.789% branch,
and 91.034% combined. Log and JSON
coverage evidence are at `/data/agentrouter-build/evidence/`. Investigate skips
before any release claim.

TASK-153 was committed and pushed as `82babba`. TASK-154 then changed the
Python bundle writer to use exclusive final-path creation. Its full regression
passes 2,604/7 with 92.021% statement, 87.833% branch, and 91.058% combined
coverage; focused tests, review, hooks, Bandit, build, and installed-wheel smoke
pass. The shared venv now points at this checkout at version `0.5.0rc1`.

TASK-154 was committed and pushed as `2542e2d`. TASK-155 makes supplied
context-band reports fail closed in Rust rather than falling back to ordinary
classification accuracy. Focused 6/6, evaluation compatibility 40/40, full Rust
workspace, strict Clippy, independent review, and full Python 2,609/7 pass.
Coverage is 92.021% statement, 87.833% branch, and 91.058% combined.

TASK-155 was committed and pushed as 613550d. TASK-156 routes one injected
Rust classifier consistently through classification, routing, safety, and
performance. Compatibility passes 42/42 and full Python passes 2,610/7 at
92.021% statement, 87.833% branch, and 91.058% combined coverage. It remains
Partial pending public default grade/runtime discovery in TASK-157.

## Recovery checkpoint — 2026-11-15

Active persistent checkout: `/home/krish/.codex/worktrees/agentrouter-production/AgentRouter-OS`,
starting detached at `c7d8180`. The old `/tmp/agentrouter-rust-next` disappeared;
TASK-153 uncommitted changes are being reconstructed. Preserve all current edits.
Python focused tests pass 88/1, Rust CLI library 75/75 and observability 6/6,
Rust workspace, strict Clippy, Python/Rust differential, independent reviews, build
and installed-wheel smoke pass. The first full Python run failed after disk exhaustion;
no coverage evidence from it is valid. A retry runs with COVERAGE_FILE in /tmp,
CARGO_INCREMENTAL=0; monitor /tmp/agentrouter-task153-retry.log and disk free space.
Next: diagnose any retry failure, record coverage, commit only verified changes.
TASK-154 patch is at /home/krish/.codex/agentrouter-recovery/task154.patch; apply
only after the running suite completes. TASK-155 identifies malformed holdout
fallback; fix and test without weakening gates. Preserve all current edits.
Hosted c7d8180 Rust, security, mutation and website pass; enforcing CI fails its release gate.
Production remains IN_PROGRESS; 29 module parity rows and external gates remain open.

## Previous checkpoint — 2026-11-15

The active RC branch is at pushed head `5af3c55`. Hosted Python, Rust, and
compatibility jobs pass across supported platforms, as do API, build, security,
website, and critical mutation. TASK-152 local Python passes 2,590/5 with
92.052% statement, 87.756% branch, and 91.064% combined coverage; Rust
workspace/Clippy, wheel/sdist, and clean-wheel smoke pass. The sole PR (#16) remains held: frozen
context-band accuracy is 0.6667 < 0.90, and it has no human review. Rust parity
is 48/77 full modules. TASK-152 currently changes shared Rust observability,
opt-in API route records, and logging redaction; commit/push to the authorized
RC, inspect hosted validation, then continue the next Partial row.
Human annotation, paid OpenAI live validation, and production credentials are
listed under Needs Krish in `PRODUCTION_STATUS.md`.

## Previous checkpoint — 2026-11-14

Active branch `release/agentrouter-v0.5-rc1`; latest pushed code is `9a7dc7a`.
TASK-150's arbitrary-precision API response differential and full Linux/Python
3.12 regression pass locally. The suite passes 2,580 tests, 5 skipped, with 92.030% statement, 87.712%
branch, and 91.038% combined coverage. Hosted critical mutation passes 1,706
selected mutants with zero unreviewed survivors. Rust workspace passes Linux,
Windows, and macOS; Linux/macOS Python/Rust compatibility passes. Windows
compatibility and most Python jobs are still running. The PR enforcing gate
fails at frozen context-band accuracy 0.6667 < 0.90. PR #16 is the only open PR
and has no GitHub reviews. Keep the PR held.

TASK-141's SDK/reliability selection, Rust workspace/Clippy, and full Python
regression pass. Current coverage evidence is
[`docs/COVERAGE_REPORT_2026-11-14-TASK-150.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-150.md).
TASK-142 compares every evaluator seed model field and Rust exports against
Python's live `__all__`. TASK-143 makes the Rust full-scorecard CLI discover the
actual sibling CLI surface at runtime. TASK-144 is pushed at `0d3ea70`: both
OpenAI adapters reject non-2xx responses, with 68 focused Python tests and
three Rust unit tests passing locally; offline differential cases cover 300,
302, and 399. Its mutation run failed the survivor-review gate; TASK-146 adds
status boundaries to the selected test suite. TASK-145 is pushed at `d80a6df`
with three complete serialized CLINC150 raw-row differentials; external dataset
fetching remains Partial. SDK, evaluator orchestration, and multiple CLI/API/MCP
modules also remain Partial in `docs/RUST_PARITY_MATRIX.md`.

TASK-146 now rejects missing/malformed OpenAI response statuses; its hosted
critical-mutation run passes with zero unreviewed survivors. TASK-147 bounds
Rust SDK TCP connection setup by the configured timeout and passes SDK
differential plus workspace checks locally. The parity matrix has 48/77 full
modules; 29 remain Partial. Next: finish the hosted matrix, continue the next
parity slice, and keep human evaluation, bounded OpenAI live validation, and
production credentials under **Needs Krish**.

## Historical narrative

> **Relationship to `AGENT_HANDOFF.md`:** `AGENT_HANDOFF.md` is the canonical live
> checkpoint and is authoritative for branch, commit, PR and next-action state.
> This file is the Codex-oriented narrative and may lag. Where the two disagree,
> `AGENT_HANDOFF.md` wins. Do not maintain a third handoff.

Last updated: 2026-08-08 (iter 26 — TASK-016 MERGED to RC; mutation gate repaired)

## Current state (iter 26)

- **Branch topology (authoritative):**
  - `main` — stable, untouched (still `602321a`). Never merge into it without explicit owner approval.
  - `release/agentrouter-v0.5-rc1` — integration branch @ `5847c22`. **NOT RELEASE READY**
    (context_band held-out 0.6667 < 0.90, unchanged). Mutation gate **PASSES**. CI is **green** on
    ordinary pushes/PRs (see below).
  - `task/TASK-011-context-band-data`, `task/TASK-012-annotation-operations`,
    `task/TASK-013-catalog-provenance`, `task/TASK-014-ci-release-semantics`,
    `task/TASK-015-trusted-catalogs` — **all MERGED to RC (PR #2/#3/#4/#5/#6) and DELETED**
    local + remote; all commits preserved via merge commits.
  - `mutation-kill-safety` — **DELETED** (local + remote); PR #1 closed as fully superseded by
    `tests/test_mutation_kills.py`.
- **TASK-011 on the RC:** `agentrouter/annotation/` program — schema, deterministic unlabelled
  candidate generation (63 prompts, all ten categories, zero frozen-holdout leaks), dedup/near-dup
  + cross-set leakage, two-annotator adjudication, leakage-safe train/dev/holdout splits, versioned
  manifests, rules/learned/hybrid comparison, optional Graphify impact (text-only fallback), and the
  `agentrouter dataset ...` CLI. Docs in `docs/CONTEXT_BAND_ANNOTATION.md`.
- **TASK-012 on the RC:** blinded per-annotator packs, resumable annotate flow, disagreements-only
  adjudication pack, JSONL+CSV export. The real two-annotator + adjudicator round is still external
  (`TASK_012_OWNER_ACTIONS.md`) — the only path to closing the honest release-gate.
- **TASK-013 on the RC:** `agentrouter/catalog_ops.py` (freshness/staleness vs
  `registry.STALE_AFTER_DAYS`, safe rollback with `.bak` backup) + `providers status` /
  `providers rollback` CLI.
- **TASK-015 on the RC:** trusted catalogs — generated catalogs carry a `provenance` block
  (source_url, fetched_at UTC, count, tool_version, cli_args) the loader ignores; atomic
  refresh (`tempfile.mkstemp` + `os.replace`); candidate-deprecation reporting on refresh
  (report-only); non-destructive backup rotation + new `providers restore`; new
  `providers doctor` that schema-validates every generated catalog and exits 3 only on real
  corruption. Independent security review: 0 critical / 3 medium / 2 low, all medium+low
  fixed and regression-tested (symlink-race on temp/backup writes, crash-instead-of-clean-fail
  on corrupt catalogs, same-second backup-rotation data loss).
- **TASK-014 on the RC:** split the always-on enforcing `release-gate` into
  `release-readiness-report` (push/PR/dispatch, non-enforcing, honest YES/NO) and
  `enforce-release-gate` (RC->main PR / release tag / explicit dispatch only, full enforcement).
  Ordinary CI is green; promotion stays strictly gated.
- **Mutation (TASK-010b CLOSED):** mutmut 3.6.0, 923 mutants — overall **0.9837**;
  `safety_policy_execution` **0.985** (>=0.95); `routing_engine` **0.9815** (>=0.85); no safety/
  auth/policy/execution-bypass survivor. `cli.execute()` gate logic extracted into undecorated
  `_execute()` for mutmut reach. Local iteration via Docker container `armut`.
- **CI on `5847c22`:** test matrix 3.10-3.13, test-windows, build-smoke, Security,
  `release-readiness-report` and **Critical Mutation Testing** all GREEN;
  `enforce-release-gate`/`live-smoke` correctly SKIP (not run) on task/RC pushes by design.
- **Local env blocker resolved (2026-08-08):** full pytest now runs cleanly on this machine (684
  passed, 3 skipped); 33 hook tests; ruff, bandit and pip-audit clean. No longer CI-only
  for regression evidence.
- **GIT GUARDRAIL REPAIRED (2026-08-08, owner-authorized):** `.claude/hooks/pre_tool_guard.py`
  had blocked `git add`/`commit`/`push` unconditionally, contradicting command.md §14 and the
  AGENTS.md git policy and making this loop impossible to execute. Now branch-aware:
  add/commit only on `task/*`; push only from a `task/*` branch for that same branch, never
  forced, never to a protected branch. **Direct writes to `main` and `release/*` are still
  refused** — record state and land every change through a task branch + PR, not by committing
  on the RC. Force push, remote-branch deletion, tags, history rewriting, `reset --hard`,
  `git clean`, recursive deletes, deployment, publication and secret printing stay blocked.
- **TASK-016 on the RC:** hosts report installed/configured/authenticated/authorized/degraded
  with a concrete remedy (offline, credential-free; existence checks only, never a network call
  or a credential read). `authorized` is never inferred offline — it needs the opt-in live check
  PHASE C lists separately, which is not implemented. Fixed a real bug: a set-but-blank API key
  used to report *available*, so `execute` would target a host that cannot authenticate.
  The critical-module mutation gate failed on the first CI run (safety_policy_execution 0.8895)
  and was repaired to 0.9877 with real tests — no threshold lowered, no mutant allowlisted.
- **Next:** remaining local backlog — benchmark routing infrastructure that needs no paid
  inference, customer docs/examples, observability runbooks, API/SDK compatibility + load
  testing (loop/BACKLOG.yaml L4/L9). Do NOT reuse/tune the frozen holdout; the 0.90 gate is unchanged; RC stays
  NOT RELEASE READY; no RC->main without owner approval.

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

