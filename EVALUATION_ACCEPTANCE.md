# Evaluation Acceptance

Acceptance state as of 2026-11-17:

| Requirement | State | Evidence |
|---|---|---|
| 100-point evaluator with seven unchanged gates | Complete | `agentrouter/evaluation/`; current grade 98.23 |
| Offline deterministic reports | Complete | `artifacts/evaluation/` JSON, Markdown, and CSV outputs |
| Separate context development/final splits | Complete | 24 development and 45 frozen holdout cases |
| Frozen holdout checksum | Complete | SHA-256 recorded and regression-tested |
| Required task/category diversity | Complete | Dataset schema and tests |
| Exact/near leakage checks | Complete | Development, gold, and test-literal comparisons |
| Accuracy, macro-F1, per-band recall, confidence intervals | Complete | Current report and result JSON |
| Immutable pre-TASK-004 comparator | Complete | Local frozen constants plus exact metric regression |
| No post-final-holdout tuning | Complete | Shipped rules-active result retained at 0.6667 |
| Strict CI/release failure behavior | Complete in code; enforcing PR check fails correctly | `--require-release-ready` in CI/release workflows |
| Held-out context threshold | **Fail** | 0.6667 < 0.90 |

All other six evaluation gates pass. This checklist does not convert a correctly
measured gate failure into acceptance.
