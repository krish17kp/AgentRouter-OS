# TASK-184 evidence

Date: 2026-11-17

The SDK test `sdk::tests::truncated_response_body_is_a_read_error_not_an_api_result`
starts a real loopback TCP listener, declares a 100-byte JSON response, sends a
short body, and verifies `SdkTransportErrorKind::ReadError`.

```console
cargo test --locked -p agentrouter-cli sdk::tests::truncated_response_body_is_a_read_error_not_an_api_result
cargo clippy --locked -p agentrouter-cli --all-targets -- -D warnings
cargo fmt --all -- --check
git diff --check
```

All commands passed locally.
