# TASK-190 evidence

Date: 2026-11-17

The Rust registry now provides a concrete `DatasetAdapter` facade in
`registry_api` with metadata, fixture/real availability, loading, preparation,
sampling, validation, checksum, and description methods. Two focused unit tests
cover a fixture-backed adapter and the explicit real-mode blocker.

```console
cargo test --locked -p agentrouter-evaluation registry_api::tests -- --nocapture
# 2 passed
cargo clippy --locked -p agentrouter-evaluation --all-targets -- -D warnings
# passed
cargo fmt --all -- --check
# passed
git diff --check
# passed
```

This does not claim full adapter parity: Rust still has no HuggingFace
`datasets` runtime, so real mode remains fail-closed and externally blocked.
