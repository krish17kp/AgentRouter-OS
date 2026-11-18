# TASK-218 Evidence

Date: 2026-11-18

## Implementation

- Added bounded `load_live_contract` transport to the Rust contract module.
- Added `contract check --live URL` with `--json` reporting and fail-closed
  compatibility status.
- Added `--baseline PATH` for explicit base-branch artifact comparisons.
- Live reports apply manifest-recorded owner acceptances as `accepted` while
  keeping the underlying changes visible.
- Redirects are disabled, credentials are never attached, response bodies are
  capped at 4 MiB, and malformed/external-reference documents are rejected.

## Verification

```text
cargo fmt --all -- --check                              # passed
cargo test --locked -p agentrouter-cli contract::tests  # 8 passed
cargo clippy --locked -p agentrouter-cli --all-targets -- -D warnings  # passed
temporary HTTP server + `contract check --live --json` # compatible=true
`contract check --baseline contracts/http/v1/openapi.json --json` # passed
recorded-acceptance Rust regression                            # passed
```

Python remains authoritative for live framework generation and hosted release
approval; this adds a Rust-side running-service verification path.
