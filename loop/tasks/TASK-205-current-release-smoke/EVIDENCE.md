# TASK-205 evidence

Date: 2026-11-17

The current optimized binary was rebuilt and exercised with an isolated home,
release-only `PATH`, and no Python environment variables. Fresh initialization,
route persistence, doctor, and MCP initialize succeeded. The default plan
correctly failed closed because the selected `claude-code` host was unavailable;
the same saved decision succeeded with `--include-unavailable --json` and
reported `execution_enabled: false` with a redacted command preview.

```console
cargo build --release --locked --workspace
cargo audit --no-yanked
# 207 dependencies scanned; no vulnerability advisories; chrono
# RUSTSEC-2026-0543 remains unmaintained with no fixed upgrade.
agentrouter --version
# agentrouter 0.5.0rc1
agentrouter init
agentrouter route "summarize a support ticket" --save --json
agentrouter plan d_00001 --json
# blocked: unavailable execution host (fail-closed default)
agentrouter plan d_00001 --include-unavailable --json
# planned, execution_enabled=false, host=claude-code
agentrouter doctor --json
# exit 0
agentrouter mcp
# initialize negotiated protocol 2025-11-25; server 0.5.0rc1
```

No provider request, command, deployment, or release promotion occurred.
