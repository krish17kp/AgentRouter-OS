# TASK-199 evidence

Date: 2026-11-17

The unified `agentrouter` binary now exposes `plan`. It loads a saved route,
passes its classification and registry model through `agentrouter-execution`,
and prints a read-only plan. The command never invokes the configured host;
the successful smoke below returned `execution_enabled: false`.

```console
cargo build --release --locked --workspace
AGENTROUTER_HOME=<fresh-home> agentrouter init
AGENTROUTER_HOME=<fresh-home> agentrouter route "summarize a support ticket" --json --save
AGENTROUTER_HOME=<fresh-home> agentrouter plan d_00001 --json
# status=planned, execution_enabled=false, host=claude-code
```

Static verification after the integration: workspace `cargo check`, strict
workspace Clippy, formatting, and the execution/orchestration focused tests
(4 + 3) pass. The package-level CLI test link was not used as release evidence
because the constrained environment exhausted the linker before the later
successful optimized binary smoke; no compiler error was observed.
