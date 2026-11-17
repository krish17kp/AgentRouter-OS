# TASK-201 evidence

Date: 2026-11-17

The optimized workspace binary was run with an isolated `HOME` and
`AGENTROUTER_HOME`, a release-only `PATH`, and `PYTHONPATH`, `VIRTUAL_ENV`, and
`CONDA_PREFIX` unset. Fresh-home `init`, `route --json --save`, and
`plan d_00001 --json` succeeded; the plan reported `execution_enabled: false`.
The same environment returned exit 0 for `doctor --json` and negotiated MCP
protocol `2025-11-25`, reporting server version `0.5.0rc1`.

This validates Rust-only runtime independence for the exercised surfaces; it
does not authorize provider execution, deployment, or release promotion.

After the orchestration guard extension, `cargo build --release --locked
--workspace` completed again and `cargo audit --no-yanked` scanned 207 locked
dependencies with no vulnerability advisories; the existing unmaintained
`chrono` warning has no fixed upgrade.
