# TASK-126 evidence

## Reproduced mismatch

Pydantic rejects confidence strings such as `" 0.0_5 "` and float registry
strings such as `" 1_0 "`, while accepting the same valid underscore forms
without surrounding whitespace. Rust previously trimmed first, then removed
digit separators, accepting the whitespace-padded forms.

## Implementation

Added a scalar visitor to the Rust core schema for Pydantic-compatible
confidence and boolean coercion. Confidence validates finite values in the
inclusive 0–1 range. Boolean conversion supports booleans, numeric 0/1 values,
and the recognized case-insensitive Pydantic tokens without trimming strings.
The registry and core float converters preserve whitespace whenever an
underscore is present, then require the numeric parser to accept the exact
remaining text.

## Verification results

- `./.venv/bin/pytest -q tests/test_rust_compat.py tests/test_cli_registry_rust_compat.py::test_rust_registry_coerces_underscored_float_strings_like_pydantic tests/test_cli_registry_rust_compat.py::test_rust_registry_rejects_whitespace_around_underscored_float_strings` — 22 passed.
- `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term` — 2,352 passed, 4 skipped, 0 failed; 91.970% statement, 87.690% branch, 90.988% combined.
- `cargo test --workspace --locked` — passed, including doctests.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — passed.
- `cargo fmt --all -- --check` — passed.
- `./.venv/bin/ruff check .` and `./.venv/bin/ruff format --check .` — passed.
- Bandit reported no issues; pip-audit and cargo audit reported no known vulnerabilities.
- `git diff --check` — passed.

Self-review covered visitor conversion, field bounds, bool token whitespace,
digit-separator positions, and the new acceptance/rejection fixtures. An
independent human review has not been obtained. Hosted CI for these changes is
pending the next authorized RC push.
