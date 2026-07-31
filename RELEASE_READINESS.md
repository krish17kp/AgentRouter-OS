# Release Readiness

**Status: NOT release-ready.** This is the canonical v0.5 release-candidate
assessment as of 2026-07-20.

## Current evidence

| Gate | State | Evidence |
|---|---|---|
| Offline routing and exact model/host output | Pass at takeover baseline | Existing routing and CLI suites |
| High-risk execution and injection protections | Pass at takeover baseline | Safety, execute, and injection suites |
| Evaluation grade | Pass | 98.32/100 from current canonical run |
| Six non-context evaluation gates | Pass | Current `artifacts/evaluation/result.json` |
| Frozen held-out context generalization | **Fail** | 0.5778 accuracy versus unchanged 0.90 threshold; 95% CI 0.4330–0.7103 |
| Safe reversible plugin lifecycle | Re-audit pending | 48 focused tests pass after the latest security repairs |
| Real mutation thresholds | Pending | Linux mutmut workflow exists; no real score is available yet |
| Final full local matrix | Pending | Baseline passed; current complete rerun remains |
| Linux/Windows GitHub checks | Pending | Release branch has not yet been pushed |
| Clean wheel install/lifecycle | Final rerun pending | Takeover baseline passed |

The 0.945 value previously used for context readiness came from the 165-case
in-sample gold set. The canonical generalization gate now uses the frozen,
checksum-locked 45-case holdout and is deliberately not tuned after its final run.

## External production prerequisites

Live provider verification, paid-model benchmarking, hosted deployment,
marketplace publication, beta feedback, and operational sign-off still require
credentials, budget, infrastructure, or owner decisions. These do not excuse the
three local/CI blockers above.
