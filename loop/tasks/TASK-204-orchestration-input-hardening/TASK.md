# TASK-204 — Orchestration input hardening

## Objective

Close malformed workflow declarations before the planning scheduler runs, while
keeping orchestration planning read-only and execution-disabled.

## Acceptance

- duplicate dependency declarations are rejected explicitly;
- empty side-effect keys are rejected before conflict scheduling;
- focused orchestration tests and strict Clippy pass;
- runtime dispatch, tool grants, workspace mutation, and cancellation remain
  clearly outside this planning-only checkpoint.
