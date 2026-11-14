# TASK-147 — Bound Rust SDK connection setup by its configured timeout

## Objective

Make the Rust SDK's native `ureq` TCP connection setup honor the same configured
timeout value that the Python SDK exposes, while retaining the existing whole
request deadline.

## Scope

- Set `ureq`'s independent connection timeout explicitly. Its pinned 2.10.1
  default is 30 seconds, and the global request timeout does not override it.
- Keep the whole-request deadline in place as an additional bound.
- Add a deterministic regression test proving a zero connection budget expires
  before attempting a local socket connection even when the overall budget is
  nonzero.
- Record the remaining native `ureq` timeout and read/write classification gaps
  honestly in the Rust parity matrix.

## Acceptance

- The default Rust SDK configures both TCP connect timeout and total request
  deadline from the client's timeout.
- The regression test proves the configured connect budget takes precedence
  over `ureq`'s 30-second default.
- Focused Rust SDK tests, Python/Rust SDK differential tests, workspace tests,
  strict Clippy, formatting, Ruff, and diff checks pass.
- Keep `agentrouter/sdk.py` Partial: the pinned `ureq` transport still exposes
  only ambiguous I/O categories for some phases and its global deadline differs
  from HTTPX's per-operation timeout model.
