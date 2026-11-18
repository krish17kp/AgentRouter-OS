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
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- status --json
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- prepare --all --json
```

`run` writes the result, scorecard, Markdown report, and classification CSV to
`artifacts/evaluation` by default. Use `--no-artifacts` for console-only output
or `--out-dir <path>` to change the output directory. `--source real` reports
unavailable external datasets as `SKIPPED_EXTERNAL`; it never substitutes a
fixture. `status --json` emits one record per registered dataset with explicit
`fixture`, `real`, and `blocker` fields. `prepare --json` emits one record per
requested dataset and preserves the distinction between a real result and an
honest `SKIPPED_EXTERNAL` blocker. Full parity with the main `agentrouter`
command tree, benchmark-specific external sources, annotation commands, and
Docker/model evaluation workflows have not been ported yet.

The Rust build includes a bounded rows-API loader for CLINC150, Banking77,
MASSIVE, LongBench v2, and SWE-bench metadata preparation. Enable network
loading explicitly with `AGENTROUTER_ENABLE_HF_REAL=1`; without that variable,
status and preparation remain offline and report the opt-in blocker. The
loader refuses redirects, caps each response at 16 MiB and each dataset at
100,000 rows, and never treats a fixture as real data.

The Rust CLI runs the same offline fixture profiles and scorecard evaluators as
the Rust library. The Python CLI remains the reference until the remaining
items in [`RUST_MIGRATION_PLAN.md`](../RUST_MIGRATION_PLAN.md) pass their CI and
release gates.
