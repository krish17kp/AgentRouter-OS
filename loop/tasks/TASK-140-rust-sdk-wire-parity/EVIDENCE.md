# TASK-140 evidence

## Verification

- Three direct Rust/Python fixture differentials pass across present, absent,
  and blank API keys. Each compares all nine operations, exact HTTP method/path,
  request JSON, decoded responses, and structured API error status, code, and
  display string.
- Cases cover trailing-slash base URL normalization, explicit `0` context
  tokens, rating `0`, empty feedback note, and `no_log=true`.
- `tests/test_rust_sdk_compat.py`, `tests/test_sdk.py`, and
  `tests/test_sdk_parity.py`: **29 passed**, including the third API-key variant.
- `cargo test --workspace --locked`: passed all crate, binary, and doctests.
- `cargo clippy --workspace --all-targets --locked -- -D warnings`: passed.
- `cargo fmt --all -- --check`, Ruff check/format for the added test, and
  `git diff --check`: passed.
- Full Python regression after the Windows fixture repair: **2,538 passed,
  5 skipped, 0 failed** in 468.91s.
  Statement coverage 92.025%, branch coverage 87.690%, combined coverage
  91.030%; evidence is in `docs/COVERAGE_REPORT_2026-11-14-TASK-140.md`.
- Pushed as `36809f5`; hosted Linux/Windows/macOS validation is running.
- The previous pushed base `52c9565` exposed one unrelated portability issue:
  Windows filtered a just-closed ephemeral TCP port as a timeout, while Python
  categorized it as a connection error. The test now targets invalid loopback
  destination port zero; the focused differential and full Python rerun pass.
  Hosted cross-platform validation for the combined repair is running at `36809f5`.

## Review and remaining contract gap

An independent diff review found no blocking correctness, security, or
cross-platform test defect. It confirmed the SDK row should remain Partial.

The fixture server binds only to loopback, returns deterministic data, records
only request shape and API-key presence/value for equality assertions, and
shuts down/join its server thread through a context manager. The Rust probe
reports generic transport failure text to avoid leaking request URLs or raw
transport details. The parity inventory keeps `agentrouter/sdk.py` Partial:
the Python constructor exposes an injectable `httpx.BaseTransport`, and Python
surfaces native `httpx` transport exception classes that the Rust SDK does not
yet model.
