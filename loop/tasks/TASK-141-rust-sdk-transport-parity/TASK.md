# TASK-141 — Rust SDK transport parity

## Objective

Match the Python SDK's injectable HTTP transport contract in Rust while keeping
credentials and request contents out of ordinary diagnostic output. Synthetic
request shapes are emitted only by the explicit test-fixture mode.

## Scope

- Add a public synchronous Rust transport trait with request, response, timeout,
  stable transport-error categories, and idempotent close behavior.
- Serialize close with in-flight sends and release the default transport's
  connection agent on close.
- Keep the default `ureq` adapter with redirects disabled and map its common
  failures to stable categories.
- Compare an injected Rust fixture transport with Python `httpx.MockTransport`
  across all nine SDK operations, including timeout values and request shape.
- Compare selected injected error classes and add Rust lifecycle/error unit
  tests.
- Reject malformed fixture-transport configuration before it can fall through
  to the default live transport and redact base URL components in fixture output.
- Redact URL, header values, and bodies from request/response debug output and
  suppress URL-bearing native transport diagnostics.

## Acceptance

- Injected Python/Rust SDK request and response differentials pass.
- Common injected error categories match their HTTPX class names.
- Rust SDK unit tests, workspace tests, strict Clippy, formatting, Python SDK
  tests, Ruff, and diff checks pass.
- The SDK row stays Partial while native `ureq` read/write I/O and timeout
  semantics remain different from HTTPX's complete behavior.
