# TASK-217 — Bundle database size no-follow

## Objective

Keep Rust diagnostic-bundle size reporting from following a database pathname
after the no-follow SQLite read has completed.

## Acceptance

- database size uses symlink metadata rather than a path-following metadata call;
- the existing no-follow open and symlink regression remain green;
- the remaining SQLite handle/sidecar race limitations stay documented.
