# TASK-183 — Release build and dependency audit

## Objective

Refresh local release-readiness evidence after the reliability and SDK slices:
build the optimized locked Rust workspace, smoke the release binary, and scan
the lockfile with the current RustSec advisory database.

## Scope

- `cargo build --release --locked --workspace`
- release binary help/version smoke
- `cargo audit --no-yanked`
- record the exact warning state without suppressing it

## Acceptance

- the optimized workspace build exits successfully;
- the release binary reports the candidate version and unified help surface;
- no vulnerability advisory is reported;
- any unmaintained-dependency warning remains visible and documented.

## Non-goals

This task does not merge, tag, publish, deploy, change audit thresholds, or
replace the frozen evaluation gate.
