# PROJECT STATUS — AgentRouter OS

**Status:** IN_PROGRESS
**Branch:** `release/agentrouter-v0.5-rc1`
**Updated:** 2026-08-08
**Canonical release ready:** NO

## Branch topology

- `main` — stable, untouched. No merge without explicit owner approval.
- `release/agentrouter-v0.5-rc1` — integration branch @ `b62ffd7` (TASK-011 PR #2,
  TASK-012 PR #3, TASK-013 PR #4, TASK-014 PR #5 all merged). NOT RELEASE READY;
  mutation gate passes, only the honest context-band `release-gate` fails (by design,
  and no longer blocks ordinary CI — see CI status below).
- `task/TASK-011-context-band-data`, `task/TASK-012-annotation-operations`,
  `task/TASK-013-catalog-provenance`, `task/TASK-014-ci-release-semantics` —
  **all merged to RC and deleted** (local + remote).
- `mutation-kill-safety` — deleted (local + remote); PR #1 closed as fully superseded by
  `tests/test_mutation_kills.py`.

## Delivered on the RC

- **TASK-010b mutation hardening** — critical-module mutation gate passes (overall
  0.9837; safety_policy_execution 0.985; routing_engine 0.9815).
- **TASK-011 context-band data & annotation program** — `agentrouter/annotation/`
  (schema, candidate generation, dedup/leakage, two-annotator adjudication,
  leakage-safe splits, versioned manifests, rules/learned/hybrid comparison,
  optional Graphify signal) + `agentrouter dataset` CLI + guidelines doc.
- **TASK-012 human annotation operations** — blinded per-annotator packs, resumable
  annotate flow, disagreements-only adjudication pack, JSONL+CSV export. Two-real-
  annotator round is still an external/owner step (`TASK_012_OWNER_ACTIONS.md`).
- **TASK-013 catalog freshness + rollback** — `agentrouter/catalog_ops.py`
  (freshness/staleness vs `registry.STALE_AFTER_DAYS`, safe rollback with backup) +
  `providers status` / `providers rollback` CLI. Provenance block and deprecation
  reconciliation were deferred and are now TASK-015's scope.
- **TASK-014 CI release-gate semantics** — split the single always-on enforcing
  `release-gate` into a non-enforcing `release-readiness-report` (push/PR/dispatch;
  honestly prints Release-ready YES/NO) and `enforce-release-gate` (RC->main PR /
  release tag / explicit dispatch only, full enforcement, no lowered thresholds).
  Ordinary RC and PR CI is green; promotion is still strictly gated.

## Why NOT release ready

`context_band_accuracy` frozen held-out = **0.6667**, below the unchanged **0.90**
gate. This is a proven dataset ceiling: rules-only 0.6667, learned-only 0.6889,
hybrid 0.6444 — none reach 0.90, and the learned model is not significantly
better than rules (overlapping CIs, lower macro-F1). Closing the gap honestly
requires a larger human-labeled dev set and new private holdout, not more
hand-rules or holdout tuning. See `KNOWN_LIMITATIONS.md`, `loop/QUALITY_GATES.yaml`,
and `loop/tasks/TASK-009-context-band-holdout/`.

The release branch is published deliberately as a **NOT-RELEASE-READY** RC to
preserve audited inherited work and exercise CI + the first real Linux mutation
run. The gate is unchanged and remains honestly failed.

## Verified locally (2026-08-08, this session, reproduced)

- Python suite: 598 collected, 595 passed, 3 env-only skips. Prior env watchdog issue
  that killed multi-second local pytest runs is **resolved** — full suite now runs in
  ~18s on this machine.
- ruff check + ruff format --check clean; bandit 0 (under `-c pyproject.toml`).
- Clean-wheel install + packaged data (`context_band_model_v1.json`) verified in
  earlier sessions; re-verification tracked under TASK-015.
- Local evaluation grade 98.23/100; 6/7 gates PASS; context-band gate FAIL (unchanged).

## CI status (release/agentrouter-v0.5-rc1 @ b62ffd7)

- **Green:** CI test matrix (3.10–3.13), test-windows, build-smoke, Security scan,
  `release-readiness-report` (non-enforcing; correctly prints Release-ready NO with
  the real context_band score).
- **Skipped by design:** `enforce-release-gate` and `live-smoke` — these now run only
  on RC->main PRs, release tags, or an explicit `workflow_dispatch` with
  `enforce_release_gate=true` (TASK-014). They do not run on task->RC pushes/PRs.
- The honest context-band gate (0.6667 < 0.90) is unchanged and will still hard-fail
  `enforce-release-gate` whenever a real RC->main promotion is attempted.

**Mutation gate now PASSES (TASK-010b closed).** Full Linux campaign (mutmut 3.6.0,
923 selected mutants): overall **0.9837**; `safety_policy_execution` **0.985** (≥0.95);
`routing_engine` **0.9815** (≥0.85); completeness + all-reviewed gates pass. No safety,
auth, policy, or execution-bypass mutant survives. The 15 remaining survivors are all
provably-equivalent mutants (dead fallback branches, `zip(strict=)` on equal-length
iterables, `round(,2)` vs `round(,3)` on finite-decimal terms, an unread parameter),
each documented in `mutation-survivor-allowlist.json`. Thresholds were NOT lowered and
no valid mutant was excluded. To make the decorated `execute()` command reachable by
mutmut, its gate + dispatch logic was extracted into an undecorated `_execute()` helper.

Repairs applied across the RC: server/SDK/observability/mcp tests guarded with
`importorskip` + `.[dev,server]` in CI test jobs; ruff format; release-readiness assertion
split into its own `release-gate` job; a real Windows bug fixed (`os.fchmod` guarded —
POSIX-only, broke every atomic plugin write on Windows); and the critical-module mutation
hardening above.

## In progress / next

- **TASK-015: trusted catalogs** — file-level provenance block, deprecation
  reconciliation on refresh, atomic refresh, rollback hardening, provider
  doctor/status. Extends TASK-013's deferred scope.
- **TASK-012 human round** — two real annotators + adjudicator still needed
  (external/owner step per `TASK_012_OWNER_ACTIONS.md`); this is the only path to
  closing the honest release-gate.
- Parallel locally-actionable engineering (host-state verification, provider
  diagnostics, benchmark routing infra, docs,
  observability/runbooks, API/SDK compatibility + load testing).

## Owner / externally blocked

- Merge RC to main, tag, PyPI/marketplace publication, deployment, paid inference,
  live provider credentials, real-user beta evidence, and the two human annotators
  required by TASK-012.
