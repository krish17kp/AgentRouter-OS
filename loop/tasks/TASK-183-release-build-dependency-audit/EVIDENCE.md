# TASK-183 evidence

Date: 2026-11-17

## Commands

```console
cargo build --release --locked --workspace
/data/agentrouter-build/target/release/agentrouter --help
/data/agentrouter-build/target/release/agentrouter --version
cargo audit --no-yanked
```

## Results

- Optimized locked workspace build: pass.
- Release binary: help surface returned successfully; version was
  `agentrouter 0.5.0rc1`.
- RustSec scan: 205 locked dependencies, no vulnerability advisories, one
  unmaintained `chrono` warning (`RUSTSEC-2026-0543`) with no fixed upgrade
  currently listed.

Full audit details are recorded in
[`docs/RUST_DEPENDENCY_AUDIT_2026-11-17.md`](../../../docs/RUST_DEPENDENCY_AUDIT_2026-11-17.md).
