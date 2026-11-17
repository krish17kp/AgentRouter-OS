# TASK-232 — Full regression recheck

## Objective

Re-run the complete Python regression suite after the release metadata and
release-evidence updates.

## Acceptance

- all tests pass with only the documented environment-dependent skips;
- any remaining warning is recorded without masking failures.
