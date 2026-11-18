# TASK-227 — Release-gate revalidation

## Objective

Re-run the authoritative release gate from the current checkout and preserve
the exact failure evidence without weakening the gate or modifying holdout
data.

## Acceptance

- all seven gate outcomes are recorded from the current command;
- the failing context-band value and release-ready status are explicit;
- the preserved historical worktree directory is identified as the only local
  dirty-state source;
- no evaluation or release inputs are modified.
