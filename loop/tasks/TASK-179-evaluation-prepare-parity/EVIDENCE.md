# TASK-179 evidence

- `cargo fmt --all -- --check` passes.
- `cargo test --locked -p agentrouter-evaluation` passes (9 crate tests).
- `cargo run --quiet --locked --bin agentrouter-evaluate -p agentrouter-evaluation -- prepare --all`
  exits 0, prints eight `SKIPPED_EXTERNAL` rows, and does not substitute
  fixture data.
- Python differential coverage adds the `prepare --all` contract assertion in
  `tests/test_rust_evaluation_cli_compat.py`; the repository checkout currently
  lacks pytest in its `.venv`, so this assertion is hosted by the normal CI
  Python matrix. The equivalent Rust command was exercised directly above.
