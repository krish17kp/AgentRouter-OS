# Rust command entry point

The Rust workspace provides a single `agentrouter` command for the migrated
surfaces. Build all sibling command executables before running the dispatcher:

```sh
cargo build --workspace --locked
cargo run --locked -p agentrouter-cli --bin agentrouter -- --help
```

`agentrouter` currently dispatches `init`, `route`, `explain`, `feedback`,
`stats`, `prompt`, `registry list`, provider status/doctor/rollback/restore,
`hosts`, `models`, `doctor`, and `dashboard` to their Rust implementations.
The human annotation flow is linked directly:

```sh
cargo run --locked -p agentrouter-cli --bin agentrouter -- dataset --help
```

`AGENTROUTER_HOME` selects the data directory; otherwise the command uses
`$HOME/.agentrouter` (or `%USERPROFILE%\.agentrouter` on Windows). `eval`
forwards to an installed `agentrouter-evaluate` executable. The remaining
Python commands—including provider refresh, plugins, contract tools, and
execution—are still migration gaps and are not claimed as Rust-compatible by
this dispatcher.
