# TASK-110 evidence

## Local verification

- Focused plugin Python/Rust compatibility: 15 passed.
- Full Python regression at the first implementation checkpoint: 2,228 passed,
  4 skipped; 6,717 / 7,234 statements, 1,896 / 2,138 branches, 91.90% combined.
- After the final Windows identity, serializer, and path corrections: Rust
  workspace tests pass; strict workspace Clippy passes with `-D warnings`;
  `cargo fmt --all -- --check` passes.
- Full Python regression after the final fixes: 2,228 passed, 4 skipped;
  6,717 / 7,234 statements, 1,896 / 2,138 branches, 91.90% combined.
- Ruff check/format and `git diff --check` pass.

## Hosted findings to resolve

The pushed `e1e8f5c` checkpoint exposed two Windows-only compatibility issues
in the pre-existing plugin read/preview slice:

1. Rust rendered a slash-separated manifest destination differently from
   Python on Windows; the corrected helper joins validated components one at a
   time so the output matches the host path contract.
2. Rust used legacy `BY_HANDLE_FILE_INFORMATION` identity while CPython 3.12+
   uses `FILE_ID_INFO` where available. The Rust reader now uses the same
   volume serial and file ID representation and fails closed if the 128-bit ID
   cannot fit the current ownership schema. The checked-in Python/Rust tests
   already cover doctor output and managed-state planning on Windows.

The full local Python regression and plugin focused suite have been rerun
after these fixes and pass. Hosted confirmation belongs to the next pushed
implementation head.
The release gate for PR #16 remains intentionally blocked at context-band
accuracy 0.6667 < 0.90; no threshold or frozen data was changed.
