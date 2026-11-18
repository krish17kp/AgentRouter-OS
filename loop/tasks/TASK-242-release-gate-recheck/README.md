# TASK-242 — Release gate recheck

## Objective

Re-run the full Python regression and canonical release gate after the route
CLI parity slice, preserving the honest gate result.

## Evidence

- Python regression: 2,747 passed, 7 expected skips, one existing dependency
  deprecation warning.
- Canonical evaluation: 165 cases, grade 98.23/100, exit 1 because only
  `context_band_accuracy>=0.90` remains false at `0.6667`.
- No holdout, threshold, or evaluation input changed.
