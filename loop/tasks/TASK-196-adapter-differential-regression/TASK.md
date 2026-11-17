# TASK-196 — Adapter differential regression

## Objective

Re-run all existing Python/Rust adapter normalization and shared-base
compatibility checks after the registry facade/factory changes.

## Acceptance

- banking77, clinc150, longbench-v2, massive, swebench, and base-contract
  differentials pass;
- no real external dataset is silently replaced by a fixture;
- exact pass count is recorded.
