# TASK-225 Evidence

Date: 2026-11-18

## Implementation

- Rust SDK response draining now maps `UnexpectedEof` to its public
  `ProtocolError` category (`RemoteProtocolError`), matching Python/httpx for
  truncated declared-length responses.
- Timeout and other read failures retain their existing categories.

## Verification

```text
cargo test --locked -p agentrouter-cli sdk::tests::truncated_response_body_is_a_protocol_error_not_an_api_result  # passed
tests/test_rust_sdk_compat.py tests/test_sdk.py                             # 23 passed
```
