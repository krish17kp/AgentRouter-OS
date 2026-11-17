# TASK-220 Evidence

Date: 2026-11-18

## Implementation

- Added `AGENTROUTER_PROJECT_ROOT` override support to the Rust evaluation CLI.
- Added current-working-directory ancestor discovery for repository roots.
- Kept the build-time Cargo-manifest fallback only as a final compatibility
  path.

## Verification

```text
cargo fmt --all -- --check                                  # passed
cargo test --locked -p agentrouter-evaluation --bin agentrouter-evaluate # passed
cargo clippy --locked -p agentrouter-evaluation --all-targets -- -D warnings # passed
cargo build --locked --workspace --release                      # passed
cargo audit --no-yanked -f Cargo.lock                           # no advisories; chrono warning only
tests/test_rust_evaluation_cli_compat.py                    # 21 passed
git diff --check                                            # passed
```

The real dataset loaders and external evaluation gates remain explicitly
blocked when their network, Docker, or credential requirements are absent.
