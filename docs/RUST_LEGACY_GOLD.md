# Rust legacy gold evaluator

The Rust evaluation crate now implements the historical classifier gold-set
report and synthetic routing-gold report from `agentrouter/evaluate.py`.
The legacy classifier thresholds are diagnostic only; they are not the frozen
context-band release gate or canonical release-readiness report.

Run the classifier gold-set evaluator from the repository root:

```console
cargo run -p agentrouter-evaluation --bin agentrouter-evaluate -- legacy-gold
```

It writes `evaluation.json`, `evaluation.md`, and `failures.csv` under
`artifacts/`. Use `--gold PATH`, `--out-dir PATH`, `--json`, or
`--no-artifacts` to select a fixture or output mode. The Rust CLI also supports
the synthetic routing scenarios:

```console
cargo run -p agentrouter-evaluation --bin agentrouter-evaluate -- routing-gold --json
```

The compatibility suite compares the complete classifier report against all
cases in `classifier_gold_v1.yaml`, exercises the injectable classifier
contract, compares Markdown and CSV artifacts, and checks every routing
scenario from `routing_gold_v1.yaml`. JSON artifact parity is compared by
parsed value because Python and Rust JSON writers escape non-ASCII text
differently while preserving the same data.

The Rust command is available for migration verification. Python remains the
shipping release authority until the remaining public-module and release gates
are complete.
