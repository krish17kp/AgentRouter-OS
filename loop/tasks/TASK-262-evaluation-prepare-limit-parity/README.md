# TASK-262 — Evaluation prepare-limit parity

## Change

`eval prepare --limit N` is now a deterministic smoke subset in both Python and
Rust. The adapter still downloads and validates the full real source first, then
reports the SHA-256-ranked subset (seed `0`) that a bounded run would consume.
Negative limits continue to produce an empty subset, matching the shared
sampling contract.

## Verification

- Python real-mode regression: 8 passed.
- Rust workspace: all tests passed; `cargo fmt --all -- --check` passed.
- No fixture fallback or external download was introduced.

This is a parity increment only. Real dataset credentials/network access,
human evaluation, release approval, and deployment remain external gates.
