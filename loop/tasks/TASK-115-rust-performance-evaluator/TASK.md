# TASK-115 — Rust performance evaluator parity

## Objective

Match the Python performance smoke evaluator's default inputs, classifier
injection seam, latency summary, and measured score in Rust. Keep machine
timings out of deterministic equality assertions and preserve the existing
thresholds.

## Implementation

- Expose the exact eight default tasks and add a Rust API that loads the
  embedded seed catalog and evaluates the defaults.
- Add `evaluate_performance_with` so callers can inject a classifier while the
  same router and score summary are measured.
- Use the shared default task catalog from Rust's aggregate evaluation runner.
- Extend the offline compatibility probe to default missing models and tasks
  from the packaged catalog and evaluator defaults.
- Add Python/Rust checks for default sample count and stable report fields,
  plus a Rust test that verifies the injected classifier runs once per task.

## Verification

The performance differential passes 6 focused cases, including default inputs
and exact fixed-sample summaries. The full Rust workspace, strict Clippy, Cargo
formatting, Ruff, and full Python regression pass. Hosted Linux, Windows, and
macOS compatibility remains part of the release-candidate check. Runtime
latency fields are intentionally not compared across machines; fixed-sample
score summaries are exact.
