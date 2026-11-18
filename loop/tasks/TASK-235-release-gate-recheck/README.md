# TASK-235 — Release-gate recheck after current package changes

## Objective

Re-run the authoritative offline release gate after the reliability entrypoint
and current-wheel changes, confirming that no release threshold or holdout data
was altered.

## Acceptance

- the command runs with the existing `--require-release-ready` threshold;
- the result and failed gate are recorded exactly;
- no evaluation inputs or thresholds are changed.
