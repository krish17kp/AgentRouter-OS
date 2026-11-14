# TASK-128 evidence

## Reproduced gaps

- Python `ModelEntry` accepts unbounded positive integers for context and token
  limits; Rust used `u32` and rejected large YAML values before field
  validation.
- Rust OpenRouter refresh narrowed context and output limits to `u32`, including
  the fallback `context_window // 4` calculation.
- Routing narrowed capacity and context-fit calculations. For large integers,
  Python's integer division can round a value just below 2.0 to 2.0, which must
  retain the Python score category.

## Implementation

- `ModelEntry` now stores exact arbitrary-precision JSON integers with positive
  Pydantic-compatible deserializers. Registry YAML normalization quotes only
  out-of-range decimal integer scalars in token-count fields before parsing;
  quoted strings retain exact numeric meaning and the scanner skips comments,
  quoted values, Unicode text, and block scalars.
- OpenRouter refresh preserves JSON integer tokens and uses exact small-divisor
  arithmetic for fallback output limits. Python's integer-only checks for live
  catalog fields remain intact.
- Routing compares arbitrary-precision capacities and uses exact midpoint
  comparisons at the Python `float` thresholds. Evaluation, API serialization,
  CLI display, and guarded OpenAI output capping were updated to the shared
  number type.

## Verification

- Full Python regression with coverage: 2,382 passed, 4 skipped, 0 failed in
  343.57s on Linux/Python 3.12.15/pytest 9.0.3. Statement coverage is 91.983%
  (6,896/7,497), branch coverage 87.735% (1,960/2,234), and weighted combined
  coverage 91.008% (8,856/9,731). The unchanged 90% statement and 85% branch
  gates pass; see `docs/COVERAGE_REPORT_2026-11-14-TASK-128.md`.
- `cargo test --workspace --locked` passes.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`
  passes.
- `cargo +1.89.0 check --workspace --all-targets --locked` passes.
- `cargo fmt --all -- --check`, Ruff check/format, Bandit, `pip-audit`,
  `cargo audit`, and `git diff --check` pass.
- Hosted CI at prior RC head `4a3e7ab` passes Rust workspace, Rust 1.89 minimum,
  and Python/Rust compatibility on Linux, Windows, and macOS. The PR #16
  promotion check still fails only at the unchanged context-band gate (0.6667
  < 0.90); live smoke is skipped without credentials. TASK-128's own hosted run
  is pending its push.

## Limits

This closes the model-token integer width/coercion mismatch for the exercised
registry, refresh, routing, evaluation, display, and guarded execution paths.
It does not establish full `agentrouter/schema.py` module parity or complete the
Rust migration. The frozen evaluation gate and owner-only release prerequisites
remain unchanged.
