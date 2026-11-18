# TASK-236 — Security and website recheck

## Objective

Re-run the current branch's Rust dependency audit and production website checks
after the release/package changes.

## Acceptance

- `cargo audit --no-yanked -f Cargo.lock` passes with only the documented
  unmaintained dependency warning;
- website lint passes with zero warnings;
- the production website build completes successfully.
