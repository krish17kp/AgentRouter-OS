# TASK-118 — Rust evaluator classifier injection

## Objective

Match Python's optional `classify_fn` seam in the routing and safety evaluator
modules while preserving each evaluator's default classifier behavior.

## Implementation

- Add generic Rust routing and safety evaluator entrypoints that accept a
  caller-provided classifier; existing entrypoints delegate to the default
  rule classifier.
- Extend the offline JSON probes with optional task-keyed classifications and
  keep the existing safety array input and routing default behavior intact.
- Add Python/Rust differential cases for complete routing and safety reports
  under injected classifications.
- Update the module inventory and release notes after verification.

## Verification

The full Python suite passes with 2,266 tests and 4 skips at 91.96% statement,
87.65% branch, and 90.97% combined coverage. Focused Python/Rust evaluator
differentials, the full Rust workspace, strict Clippy, formatting, Ruff, and
diff checks pass locally. Hosted Windows confirmation is pending.
