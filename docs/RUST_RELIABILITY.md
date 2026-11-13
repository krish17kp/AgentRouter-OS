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
- Redirects are not followed, matching the Python HTTP client's default and
  preventing a local test request from being forwarded to another host.

The Rust slice does not launch or stop the API server, expose Python's arbitrary
request callable, or reproduce Python's individual transport exception names.
Those contracts remain in Python and the matrix marks the reliability modules
Partial.

## Differential verification

`tests/test_rust_reliability_compat.py` compares load and soak result shapes,
drives the Rust binary against a real Python HTTP server, checks request ID
uniqueness, and verifies that a redirect target is not contacted. The same
file runs in the Linux, Windows, and macOS Python/Rust compatibility workflow.

The `reliability_from_json` binary is a test bridge, not a stable user-facing
command. It accepts one JSON object on standard input. For example:

```json
{"operation":"summarize_load","outcome":{"statuses":{"200":12},"transport_errors":{},"latencies_ms":[4,5,6],"elapsed_seconds":0.5,"request_ids":["a","b","c"]}}
```
