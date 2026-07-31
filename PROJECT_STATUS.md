# PROJECT STATUS — AgentRouter OS

**Status:** IN_PROGRESS
**Branch:** `release/agentrouter-v0.5-rc1`
**Updated:** 2026-07-31
**Canonical release ready:** NO

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

## Verified locally (prior sessions, reproduced)

- Python suite: 481 collected, 480 passed, 1 env-only skip (OpenTelemetry).
- ruff clean; bandit 0 (under `-c pyproject.toml`).
- Clean-wheel install + packaged data (`context_band_model_v1.json`) verified.
- TypeScript SDK typecheck + 8/8 tests; hook tests pass.
- Local evaluation grade 98.23/100; 6/7 gates PASS; context-band gate FAIL.

## CI status (release/agentrouter-v0.5-rc1 @ 156928d)

- **Green:** CI test matrix (3.10–3.13), test-windows, build-smoke, Security,
  **`Critical Mutation Testing`**.
- **Red (honest, by design):** `release-gate` — context-band held-out 0.6667 < 0.90.
  This is the only failing check and is intentional; the branch stays NOT RELEASE READY.

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

- TASK-011: context-band data + annotation program (new dev set + private holdout) —
  the only remaining path to closing the honest release-gate.

## Owner / externally blocked

- Merge to main, tag, PyPI/marketplace publication, deployment, paid inference,
  live provider credentials, real-user beta evidence.
