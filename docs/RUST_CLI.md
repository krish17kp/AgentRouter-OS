# Rust command entry point

The Rust workspace provides a single `agentrouter` command for the migrated
surfaces. Build all sibling command executables before running the dispatcher:

```sh
cargo build --workspace --locked
cargo run --locked -p agentrouter-cli --bin agentrouter -- --help
```

`agentrouter` currently dispatches `init`, `route`, `explain`, `feedback`,
`execute`, `stats`, `prompt`, `registry list`, provider status/doctor/refresh/rollback/restore,
`hosts`, `models`, `doctor`, the local HTTP API (`server`), stdio MCP
(`mcp`), and `dashboard` to their Rust implementations. The server defaults
to `127.0.0.1:8000`; set `AGENTROUTER_API_KEY` to require API authentication.
Both services run inside the unified executable and use its selected
`AGENTROUTER_HOME` directory.

`execute <decision-id>` revalidates the stored safety gate. Execution is
provider-opt-in and requires `--yes`; `--dry-run` always runs nothing. OpenAI
Responses requests require `OPENAI_API_KEY` and are sent once without retries.
The human annotation flow is linked directly:

```sh
cargo run --locked -p agentrouter-cli --bin agentrouter -- dataset --help
```

`AGENTROUTER_HOME` selects the data directory; otherwise the command uses
`$HOME/.agentrouter` (or `%USERPROFILE%\.agentrouter` on Windows). `eval`
forwards to an installed `agentrouter-evaluate` executable. Provider refresh
supports `openrouter` and `openai` with `--limit`, `--match`, and
`--dry-run`; OpenAI refresh requires `OPENAI_API_KEY`. The remaining Python
commands—including plugins and contract tools—are still migration gaps and are
not claimed as Rust-compatible by this dispatcher.
