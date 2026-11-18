# TASK-185 evidence

Date: 2026-11-17

The Rust plugin doctor now checks destination path components before probing
transaction or ownership state. A symlinked root produces an actionable
blocked-destination finding instead of the misleading “check itself failed”
message. The focused Unix regression passes, and a local doctor smoke against
the real symlinked `~/.claude` root reproduces the corrected output.

```console
cargo test --locked -p agentrouter-cli plugins::tests::diagnose_reports_linked_plugin_root_as_blocked_destination
cargo clippy --locked -p agentrouter-cli --all-targets -- -D warnings
cargo fmt --all -- --check
git diff --check
```
