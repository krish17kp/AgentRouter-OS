# TASK-140 — Rust SDK wire-contract parity

## Objective

Establish differential evidence that the Rust synchronous client sends the
same requests and exposes the same decoded API responses and structured API
errors as `agentrouter.sdk.AgentRouterClient`.

## Scope

- Exercise all nine public client operations against one deterministic local
  HTTP fixture in Python and Rust.
- Compare methods, paths, JSON bodies, API-key headers, successful decoded
  values, and structured error fields/display.
- Cover present, absent, and blank API keys; trailing slash normalization;
  explicit zero/empty optional fields; and `no_log=true`.
- Keep the module Partial where the Python injectable transport and native
  transport exception contract do not have Rust equivalents.

## Acceptance

- Python/Rust differential tests pass on Linux, Windows, and macOS CI.
- Full Rust workspace and strict Clippy pass.
- SDK parity is not overstated while public constructor/error behavior differs.
- Test bridge output does not expose URLs, credentials, or raw transport errors.
