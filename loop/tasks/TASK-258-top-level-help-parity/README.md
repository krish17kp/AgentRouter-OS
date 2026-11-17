# TASK-258 — Top-level prompt help parity

## Evidence

- The unified Rust top-level help now advertises the complete public prompt
  generation syntax: optional task text, `--from`, `--tool`, and `--out`.
- `tests/test_rust_unified_cli_compat.py::test_help_and_version_are_available`
  passes, including the exact syntax assertion.
- `cargo fmt --all -- --check` passes.

This is a documentation/help-contract correction only. It does not change
prompt generation behavior, evaluation inputs, release thresholds, or
production deployment state.
