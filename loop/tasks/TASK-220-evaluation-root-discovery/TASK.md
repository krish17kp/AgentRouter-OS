# TASK-220 — Relocatable Rust evaluation root discovery

## Objective

Make the Rust evaluation and annotation CLI usable outside the build checkout
without silently pointing at the machine where it was compiled.

## Acceptance

- `AGENTROUTER_PROJECT_ROOT` explicitly selects the project/data tree;
- absent an override, the CLI discovers a repository ancestor from the current
  working directory before using the build-time fallback;
- fixture discovery, dataset listing, and annotation pack defaults work from a
  relocated tree;
- existing evaluation behavior and external-data blockers remain unchanged.
