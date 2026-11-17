# TASK-184 — SDK truncated-response regression

## Objective

Cover the native Rust SDK's real socket behavior when an HTTP peer declares a
larger response body than it sends. Python/httpx treats that as a transport
read failure; the Rust client must not parse or classify the partial payload as
an API response.

## Acceptance

- a loopback server can reproduce the declared-length/truncated-body case;
- the SDK returns `ReadError`, not a successful JSON value or API error;
- focused tests, strict Clippy, formatting, and diff checks pass.

## Non-goals

This does not claim complete native read/write phase taxonomy; that remains a
known `ureq` limitation and keeps the SDK parity row Partial.
