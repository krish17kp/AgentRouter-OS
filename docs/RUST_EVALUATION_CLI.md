# Rust evaluation CLI

The Rust workspace provides a separate `agentrouter-evaluate` command for
running the offline evaluation workflow while the Python `agentrouter evaluate`
commands remain the shipping authority.

Run commands from the repository root:

```console
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- list-datasets
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- validate-dataset agentrouter-gold
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- run --profile fast --json
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- run --profile nightly --all --json
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- status
```

`run` writes the result, scorecard, Markdown report, and classification CSV to
`artifacts/evaluation` by default. Use `--no-artifacts` for console-only output
or `--out-dir <path>` to change the output directory. `--source real` reports
unavailable external datasets as `SKIPPED_EXTERNAL`; it never substitutes a
fixture. Real Hugging Face loading/preparation, annotation commands, and full
parity with the main `agentrouter` command tree have not been ported yet.

The Rust CLI runs the same offline fixture profiles and scorecard evaluators as
the Rust library. The Python CLI remains the reference until the remaining
items in [`RUST_MIGRATION_PLAN.md`](../RUST_MIGRATION_PLAN.md) pass their CI and
release gates.
