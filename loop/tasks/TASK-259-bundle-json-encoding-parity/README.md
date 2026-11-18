# TASK-259 — Diagnostic bundle JSON encoding parity

## Evidence

- Rust diagnostic-bundle JSON artifacts now escape non-ASCII characters with
  Python `json.dumps`-compatible `\\uXXXX` sequences, including surrogate
  pairs for non-BMP code points.
- Added a Rust regression for accented and emoji content; the focused bundle
  and diagnostics differential selection passes 45 tests.
- The `agentrouter-cli` crate passes strict Clippy and the workspace formatter.

The change preserves the existing allowlist, redaction, byte bounds, and
no-overwrite safety behavior. It does not alter evaluation inputs or release
gates.
