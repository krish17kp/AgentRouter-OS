# Quality Dashboard — AgentRouter OS

_Last refreshed: 2026-08-08 (iter24, after TASK-011/012/013/014 merged to the RC
@ `b62ffd7`). Current measurements supersede historical TASK-004 in-sample
readiness claims._

| Dimension | Current state | Evidence |
|---|---|---|
| Python tests | Pass | `pytest` 595 passed, 3 env-skips (2026-08-08, local); includes TASK-011/012/013 tests; local env watchdog issue that previously killed multi-second runs is resolved |
| TypeScript SDK | Pass (prior session) | `npm test` 8/8 and `npm run typecheck` |
| Hooks | Pass (prior session) | `.claude/hooks/test_hooks.py`: 15 passed |
| Lint | Pass | Ruff check + format clean across the tree (verified 2026-08-08) |
| Evaluation grade | ~98/100 | `python -m agentrouter eval run --all --out-dir artifacts/evaluation` |
| Evaluation gates | **6/7; release readiness NO** | Frozen 45-case context holdout accuracy 0.6667 (rules-active), below the unchanged 0.90 threshold |
| Mutation | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985; routing_engine 0.9815; no safety/policy/execution-bypass survivor |
| Security | Pass | Bandit 0 (config-aware, verified locally 2026-08-08) + pip-audit green on RC CI |
| Packaging | Pass (prior session; TASK-015 re-verifies) | Wheel + clean-venv CLI/resources/API/MCP smoke; packaged context-band candidate pool loads |
| GitHub CI (RC) | Pass; enforce-release-gate correctly gated to promotion only | Matrix 3.10-3.13 + test-windows + build-smoke + Security + release-readiness-report green on `b62ffd7`; `enforce-release-gate`/`live-smoke` skip on task/RC pushes by design (TASK-014) |
| Context-band dataset program | Delivered | TASK-011/012 merged (annotation CLI, adjudication, leakage-safe splits, comparison); final human labels are the external TASK-012 step |
| Catalog freshness + rollback | Delivered (provenance/deprecation deferred to TASK-015) | TASK-013 merged: `providers status`/`providers rollback` |
| CI release-gate semantics | Delivered | TASK-014 merged: report/enforce split |

## Canonical evaluation gates

- `task_type_macro_f1>=0.90`: PASS
- `high_risk_recall==1.00`: PASS
- `approval_accuracy==1.00`: PASS
- `tool_needs_f1>=0.90`: PASS
- `context_band_accuracy>=0.90`: **FAIL (0.6667; shipped rules-active)**
- `high_risk_gated==1.00`: PASS
- `synthetic_routing_top1>=0.95`: PASS

The former 0.945 context value is explicitly labeled as in-sample gold-set
accuracy in the current report. It is not evidence of held-out generalization.

## Open release blockers

- Frozen held-out context-band accuracy (0.6667) is below the unchanged 0.90
  threshold. This is the sole remaining blocker; it needs the human-labelled
  dataset from TASK-011 tooling + TASK-012 operations, not tuning.
- (Resolved) Linux mutation score: overall 0.9837, all gates pass.
- (Resolved) Full verification matrix + release-branch GitHub checks: green except
  the honest release-gate above.
