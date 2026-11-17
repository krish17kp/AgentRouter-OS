# TASK-229 — Installed-wheel smoke

## Objective

Prove that the freshly built release wheel works outside the source checkout.

## Acceptance

- isolated installation succeeds;
- installed version and `init` succeed;
- installed `route --json` succeeds without a provider call or source-tree
  import dependency.
