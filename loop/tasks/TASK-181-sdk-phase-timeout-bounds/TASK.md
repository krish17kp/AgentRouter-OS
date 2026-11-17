# TASK-181 — Rust SDK phase timeout bounds

## Contract

The default Rust SDK transport must bound connect, read, and write phases with
the configured timeout, while preserving the existing aggregate request
deadline and redirect refusal.

## Scope

- apply the configured timeout to `ureq` connect, read, and write operations;
- retain the aggregate request timeout as the final cap;
- keep the existing credential-safe diagnostics and transport categories;
- do not claim full SDK parity until native read/write error classification is
  differentially covered.
