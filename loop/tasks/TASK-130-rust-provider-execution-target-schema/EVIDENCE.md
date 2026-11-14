# TASK-130 evidence

## Gap

`ExecutionTarget` had been exercised only as a nested registry field, and
`Provider` had no direct Python/Rust roundtrip probe or Rust serializer. That
left the public classes' own defaults, custom boolean coercions, and invalid
input behavior unverified independently of `load_models`/`load_providers`.

## Implementation

- Added a Rust JSON probe for direct `ExecutionTarget` and `Provider`
  deserialization/serialization.
- Derived canonical JSON serialization for Rust `Provider`.
- Added accepted and rejected direct Pydantic differential cases for defaults,
  enum selection, nested string lists, boolean coercions, required fields, and
  extra/invalid values.

## Verification

- Focused schema and registry compatibility suites: 101 passed.
- Full Python regression: 2,405 passed; 4 skipped; 0 failed in 416.38 seconds.
- Coverage: 91.970% statements (6,895/7,497), 87.690% branches
  (1,959/2,234), and 90.988% weighted combined (8,854/9,731); evidence is in
  [`docs/COVERAGE_REPORT_2026-11-14-TASK-130.md`](../../../docs/COVERAGE_REPORT_2026-11-14-TASK-130.md).
- `cargo test --workspace --locked`: passed.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`:
  passed.
- `cargo fmt --all -- --check`, targeted Ruff, and `git diff --check`: passed.
- Hosted Python/Rust and Python platform checks are running at `83fd7dc`; the
  frozen context-band gate remains below threshold, and hosted validation of
  this unpushed TASK-130 change is pending.
