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

## In progress

- First real Linux mutation CI (`.github/workflows/mutation.yml`) — score pending
  first GitHub Actions run.
- Release-branch GitHub check repair.
- TASK-011: context-band data + annotation program (new dev set + private holdout).

## Owner / externally blocked

- Merge to main, tag, PyPI/marketplace publication, deployment, paid inference,
  live provider credentials, real-user beta evidence.
