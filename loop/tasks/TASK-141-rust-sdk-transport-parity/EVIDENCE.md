# TASK-141 evidence

## Local verification

- Python/Rust injected transport tests exercise all nine operations with
  authenticated requests, request bodies/content types, normalized URLs,
  response decoding, structured API errors, and equal HTTPX/Rust timeout values.
- Selected injected failures compare ConnectError, ConnectTimeout, ReadTimeout,
  and RemoteProtocolError categories.
- Rust SDK unit tests cover request delivery, stable error categories, idempotent
  close, and rejection after close.
- Malformed fixture definitions fail closed before the bridge can construct a
  live transport; fixture mode still requires explicit test opt-in.
- Fixture output records only the endpoint suffix, redacting URL userinfo,
  query strings, host, and base path.
- `SdkRequest` and `SdkResponse` debug output omits URL, header values, and raw
  bodies; native `ureq` errors use a safe message instead of echoing the URL.
- The default Rust adapter and Python `httpx` both report
  `UnsupportedProtocol` for an unsupported URL scheme without opening a socket.
- Close waits for active transport sends before closing the adapter; the
  default adapter drops its `ureq::Agent` immediately. Tests cover close/send
  ordering, idempotent close, and requests after close.
- Cross-platform reliability coverage uses that unsupported scheme because
  port-zero behavior was not stable on the Windows runner.
- Focused SDK/reliability Python selection: 52 passed. Rust SDK unit tests: 9
  passed; full workspace and strict Clippy pass locally.
- Full Python regression: 2,550 passed, 5 skipped in 408.95 seconds; coverage
  is 92.025% statement, 87.690% branch, and 91.030% combined in
  `docs/COVERAGE_REPORT_2026-11-14-TASK-141.md`.
- Hosted cross-platform CI is pending the authorized RC push.

## Contract limits

The Rust SDK exposes a stable transport trait and typed categories, but default
`ureq` cannot always tell generic write I/O from read I/O, and its timeout model
is not identical to HTTPX. Keep `agentrouter/sdk.py` Partial until those native
transport differences are fully measured and resolved.
