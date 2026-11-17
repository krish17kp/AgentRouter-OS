# TASK-265 — MASSIVE locale-fetch parity

## Outcome

Rust real-mode MASSIVE collection now receives the requested language list at
the loader boundary and fetches only those Hugging Face locale configs. This
matches Python `MassiveAdapter(languages=...)`; an empty list remains
equivalent to no filter, and unknown language codes fail before any fetch.

## Evidence

- `cargo test --workspace`: pass (including 15 `agentrouter-evaluation` tests
  and 90 `agentrouter-cli` tests).
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`:
  pass.
- `cargo fmt --all -- --check`: pass.
- `.venv/bin/pytest -q tests/test_rust_evaluation_collect_compat.py tests/test_rust_evaluation_registered_runner_compat.py tests/test_rust_evaluation_cli_compat.py tests/test_rust_evaluation_adapter_base_compat.py`:
  58 passed.

## Scope boundary

This is a parity and bounded-fetch improvement only. External dataset
credentials/network availability, broader adapter lifecycle parity, frozen
human evaluation, hosted release approval, and deployment remain open gates.
