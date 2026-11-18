# TASK-234 — Current wheel rebuild and smoke

## Objective

Rebuild release artifacts after the reliability package entrypoint change and
verify that the installed wheel exposes that entrypoint alongside the existing
CLI lifecycle.

## Acceptance

- current sdist and wheel build successfully;
- `twine check` passes for both artifacts without metadata warnings;
- an isolated wheel install reports the version, package-level reliability help,
  initialization, and local routing successfully.
