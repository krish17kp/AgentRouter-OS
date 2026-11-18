# TASK-129 evidence

## Reproduced gap

Rust's `Ability` deserializer accepted values from 0 through 255, and relied on
`ModelEntry::validate` to reject scores above 10. Python's public `Ability`
model applies the 0–10 field bound immediately, so direct Rust deserialization
accepted values that Python rejected.

## Implementation

- Bound each Rust ability score in its field deserializer to the same inclusive
  range as Pydantic, while preserving Pydantic-compatible bool, integral float,
  and integer-string coercions.
- Added a JSON probe for the public Rust `Ability` type and direct accepted and
  rejected Python/Rust differential cases.

## Verification

- `tests/test_rust_schema_compat.py` and
  `tests/test_cli_registry_rust_compat.py`: 88 passed.
- `cargo test --locked -p agentrouter-registry`: 23 passed; binary and doc-test
  targets pass.
- Full Python regression with coverage: 2,392 passed, 4 skipped, 0 failed in
  418.55s on Linux/Python 3.12.15/pytest 9.0.3. Statement coverage is 91.970%
  (6,895/7,497), branch coverage 87.690% (1,959/2,234), and weighted combined
  coverage 90.988% (8,854/9,731); the 90%/85% gates pass. See
  `docs/COVERAGE_REPORT_2026-11-14-TASK-129.md`.
- `cargo test --workspace --locked` passes.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`
  passes.
- Strict package Clippy, full Rust formatting check, Ruff check and format for
  the new test pass.
- Hosted TASK-129 checks are running at RC commit `83fd7dc`.
