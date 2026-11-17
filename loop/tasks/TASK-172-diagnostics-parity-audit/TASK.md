# TASK-172 — Diagnostics parity audit

Audit the structured `agentrouter doctor` surface after provider refresh parity.
The Rust doctor already has isolated checks, fail-closed database/registry
handling, plugin rollups, opt-in usage checks, and secret-safe bundles. This
increment aligns stable product-facing summaries with Python and adds direct
cross-language evidence without pretending runtime-specific Rust checks are
Python checks.

## Baseline

`tests/test_diagnostics_rust_compat.py` has 40 compatibility checks. The Rust
report had the same stable IDs but reported `agentrouter-rust-cli 0.1.0`, a
Rust-specific server-extra summary, and a shortened contract summary where the
Python report exposes the product version, installed server extra, and contract
directory. The diagnostics row remains Partial because runtime-specific checks,
OTel capability discovery, and complete bundle field parity are still distinct.

## This increment

- Align `app.version`, `server.extra`, and `contract.version` stable summaries
  with Python's public report.
- Add a direct Python/Rust assertion for those stable checks.
- Preserve the Rust-specific `runtime.rust` check and document the remaining
  runtime/bundle differences honestly.

## Evidence

The Rust doctor now reports the package version as `agentrouter-os 0.5.0rc1`,
uses the same server-extra wording, and includes the contract directory in its
summary. The direct Python/Rust stable-check differential passes, along with
the full diagnostics compatibility suite (41 tests), Rust diagnostics tests,
and strict Clippy. The module remains Partial because the Rust runtime check,
OTel capability discovery, and complete bundle field parity are intentionally
not represented as Python runtime checks.
