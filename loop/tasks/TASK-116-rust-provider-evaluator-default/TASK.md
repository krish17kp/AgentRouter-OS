# TASK-116 — Rust provider evaluator defaults

## Objective

Complete the provider evaluator's default-input behavior in Rust so a no-models
call evaluates the packaged seed registry just as Python does, while retaining
exact caller-supplied catalog behavior.

## Implementation

- Add a Rust default evaluator that uses the validated embedded provider/model
  catalog loader.
- Keep the JSON compatibility probe backward compatible with its existing
  top-level model-array fixture and accept an omitted `models` field.
- Add a Python/Rust differential for the no-argument evaluation result.
- Update the public-module parity matrix and release notes.

## Verification

The explicit-catalog and default-catalog Python/Rust differentials pass. The
full Python suite passes with 2,263 passed and 4 skipped at 91.96% statement,
87.65% branch, and 90.97% combined coverage. The full Rust workspace,
all-target/all-feature strict Clippy, and formatting pass locally. Hosted
Linux/macOS checks pass on the preceding candidate; hosted Windows execution
must confirm the current no-replace rename repair before this increment is
promoted.
