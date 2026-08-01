# Quality Dashboard — AgentRouter OS

_Last refreshed: 2026-07-31 (iter21, after TASK-011 merged to the RC). Current
measurements supersede historical TASK-004 in-sample readiness claims._

| Dimension | Current state | Evidence |
|---|---|---|
| Python tests | Pass | `pytest` 583+ passed, 1 env-skip (otel); includes 26 TASK-011 annotation tests |
| TypeScript SDK | Pass | `npm test` 8/8 and `npm run typecheck` |
| Hooks | Pass | `.claude/hooks/test_hooks.py`: 15 passed |
| Lint | Pass | Ruff check + format clean across the tree |
| Evaluation grade | ~98/100 | `python -m agentrouter eval run --all --out-dir artifacts/evaluation` |
| Evaluation gates | **6/7; release readiness NO** | Frozen 45-case context holdout accuracy 0.6667 (rules-active), below the unchanged 0.90 threshold |
| Mutation | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985; routing_engine 0.9815; no safety/policy/execution-bypass survivor |
| Security | Pass | Bandit 0 (config-aware) + pip-audit green on RC CI |
| Packaging | Pass | Wheel + clean-venv CLI/resources/API/MCP smoke; packaged context-band candidate pool loads |
| GitHub CI (RC) | Pass except release-gate | Matrix 3.10-3.13 + test-windows + build-smoke + Security + Critical Mutation Testing green; only the honest context-band release-gate is red |
| Context-band dataset program | Delivered | TASK-011 merged (annotation CLI, adjudication, leakage-safe splits, comparison); final human labels are the TASK-012 external step |

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
