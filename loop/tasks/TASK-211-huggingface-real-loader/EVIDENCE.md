# TASK-211 Evidence

Date: 2026-11-17

## Implementation

- Added a fixed-HTTPS Hugging Face datasets-server rows client to the Rust
  evaluation crate.
- Added 20-second connect/read/write bounds, redirect refusal, a 16 MiB
  response cap, and a 100,000-row cap.
- Added adapter wiring for CLINC150, Banking77, MASSIVE, LongBench v2, and
  SWE-bench metadata preparation through the existing Rust normalizers.
- Kept network loading opt-in with `AGENTROUTER_ENABLE_HF_REAL=1`; the default
  offline path still reports an explicit blocker.

## Verification

```text
2 local bounded-loader tests passed
14 Rust evaluation unit tests passed
cargo fmt --all -- --check  # passed
cargo clippy --locked -p agentrouter-evaluation --all-targets -- -D warnings  # passed
20 passed in 5.14s  # tests/test_rust_evaluation_cli_compat.py
2740 passed, 5 skipped  # full Python regression suite
```

Live public endpoint probe:

```text
AGENTROUTER_ENABLE_HF_REAL=1 ... prepare --dataset banking77 --json
REAL, 3079 normalized records, no fixture fallback
```

CLINC150 was rate-limited on a subsequent public probe; that remains an
honest external result rather than a fabricated success.

The first full regression attempt exposed 19 public-surface differences in
blocker wording and Hugging Face aliases. Those were repaired without changing
the Python contract; the authoritative rerun then passed 2,740 tests with 5
skips.
