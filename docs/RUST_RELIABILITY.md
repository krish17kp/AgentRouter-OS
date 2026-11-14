# Rust reliability harness

`agentrouter-reliability` provides Rust load-result and soak-result models plus
a concurrent HTTP load runner. It is a migration slice for the Python
`agentrouter.reliability` package; Python remains the release authority.

## Current surface

- `LoadSpec` builds the default `/v1/route` request or accepts a Rust request
  factory.
- `run_load` sends a fixed number of requests through a worker pool and records
  HTTP statuses, transport failures, request IDs, and indicative timing data.
- `LoadOutcome::as_dict` preserves the Python result fields. Latency values are
  reported and never used as a release threshold.
- `Sample`, `SoakResult`, and `soak` produce resource trend reports while
  repeatedly calling an already-running API process.
- `serve_app` starts the Rust API router on an ephemeral loopback port;
  `serve_router` accepts a caller-supplied Axum router for local tests. The
  returned `RunningApp` owns graceful shutdown, joins its server thread, and
  shuts down on drop. It binds only to `127.0.0.1`.
- Redirects are not followed, matching the Python HTTP client's default and
  preventing a local test request from being forwarded to another host.

The reliability crate has the in-process server lifecycle needed for local
load tests, but it does not yet match the Python soak CLI's initialization,
output, and exit-code behavior. Rust groups transport failures under
`TransportError` instead of reproducing each `httpx` exception class. Resource
sampling is also intentionally platform-limited (`/proc` file descriptors and
Unix `getrusage`); timing and resource measurements remain report-only. The
parity matrix therefore keeps these modules Partial.

## Differential verification

`tests/test_rust_reliability_compat.py` compares load and soak result shapes,
drives the Rust binary against a real Python HTTP server, checks request ID
uniqueness, and verifies that a redirect target is not contacted. The same
file runs in the Linux, Windows, and macOS Python/Rust compatibility workflow.
The lifecycle check separately starts the built-in Rust API, drives `/health`,
stops it twice, and confirms that the loopback endpoint is closed afterward.

The `reliability_from_json` binary is a test bridge, not a stable user-facing
command. It accepts one JSON object on standard input. For example:

```json
{"operation":"summarize_load","outcome":{"statuses":{"200":12},"transport_errors":{},"latencies_ms":[4,5,6],"elapsed_seconds":0.5,"request_ids":["a","b","c"]}}
```
