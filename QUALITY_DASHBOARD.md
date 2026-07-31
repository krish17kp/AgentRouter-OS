# Quality Dashboard — AgentRouter OS

_Last refreshed: 2026-07-20 during the v0.5 release-candidate takeover. Current
measurements supersede historical TASK-004 in-sample readiness claims._

| Dimension | Current state | Evidence |
|---|---|---|
| Python tests | Reverification in progress | Last full baseline: 427 passed; current focused suites: plugins 48 passed, context holdout 9 passed, mutation harness 8 passed |
| TypeScript SDK | Pass | `npm test` 8/8 and `npm run typecheck` passed at takeover baseline |
| Hooks | Pass | `.claude/hooks/test_hooks.py`: 15 passed at takeover baseline |
| Lint | Pass for current TASK-008 scope | Ruff check and format passed for plugin implementation/tests; full-tree rerun pending |
| Evaluation grade | 98.32/100 | `python -m agentrouter eval run --all --out-dir artifacts/evaluation` |
| Evaluation gates | **6/7; release readiness NO** | Frozen 45-case context holdout accuracy 0.5778, below the unchanged 0.90 threshold |
| Mutation | Harness complete; real score pending | Linux-only mutmut 3.6.0 workflow is implemented; no score is claimed before its first GitHub run |
| Security | Baseline pass; final rerun pending | Bandit and pip-audit passed at takeover baseline; final secret/security scans remain in the release matrix |
| Packaging | Baseline pass; final rerun pending | Wheel, clean-environment CLI/resources/API/MCP smoke passed at takeover baseline |
| GitHub CI | Pending | Release branch has not yet been pushed; Linux/Windows and mutation checks have no current run evidence |

## Canonical evaluation gates

- `task_type_macro_f1>=0.90`: PASS
- `high_risk_recall==1.00`: PASS
- `approval_accuracy==1.00`: PASS
- `tool_needs_f1>=0.90`: PASS
- `context_band_accuracy>=0.90`: **FAIL (0.5778; Wilson 95% CI 0.4330–0.7103)**
- `high_risk_gated==1.00`: PASS
- `synthetic_routing_top1>=0.95`: PASS

The former 0.945 context value is explicitly labeled as in-sample gold-set
accuracy in the current report. It is not evidence of held-out generalization.

## Open release blockers

- Frozen held-out context-band accuracy is below the unchanged release threshold.
- A real Linux mutation score and reviewed-survivor report do not exist until CI runs.
- The final full verification matrix and release-branch GitHub checks are pending.
