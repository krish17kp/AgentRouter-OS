# TASK-147 evidence

## Implementation

- The Rust SDK previously set only `AgentBuilder::timeout`. In pinned `ureq`
  2.10.1, TCP connection timeout is configured separately and defaults to 30
  seconds; the overall timeout does not override an explicit connection timeout.
- The native adapter now derives both `timeout_connect` and the existing overall
  request deadline from the SDK client's configured timeout. This preserves the
  stricter whole-call bound while removing the unrelated 30-second connect wait.
- A deterministic unit test sets a zero connect budget with a two-second overall
  budget and confirms the connection phase expires before opening the local
  socket.
- Reference: [ureq 2.10.1 `AgentBuilder` documentation](https://docs.rs/ureq/2.10.1/ureq/struct.AgentBuilder.html).

## Local verification

- Focused Rust SDK tests: 10 passed.
- Python/Rust SDK and Python SDK differential selection: 41 passed.
- Rust workspace tests: passed.
- Rust formatting and strict Clippy: passed.
- Ruff check and formatting for the Python SDK differential test module: passed.
- `git diff --check`: passed.
- The change is pushed at `aafede0`. Hosted Rust workspace and Python/Rust
  compatibility checks pass on Linux, Windows, and macOS at `c1b6750`.
- The refreshed Linux/Python 3.12 full suite passes 2,570 tests with 5 skips;
  statement/branch/combined coverage is 92.030%/87.712%/91.038% in
  [`docs/COVERAGE_REPORT_2026-11-14-TASK-147.md`](../../../docs/COVERAGE_REPORT_2026-11-14-TASK-147.md).

## Remaining contract gap

The overall `ureq` deadline is not identical to HTTPX's per-operation timeout
model. `ureq` also loses read-versus-write phase information for some transport
errors. Keep the SDK module Partial until those behaviors are measured and
resolved.
