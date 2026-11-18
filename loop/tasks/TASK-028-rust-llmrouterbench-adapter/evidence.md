# TASK-028 — Rust LLMRouterBench adapter parity

## Contract covered

Ported the complete LLMRouterBench adapter behavior: fixture loading, metadata,
availability, real-mode skipped-external reason, model-mapping requirement and
note, full-run status and commands, description, seeded sampling, and checksum.
The matrix marks this adapter module Parity.

## Differential evidence

- Exact Python/Rust comparison covers the complete adapter output, all fixture
  cases, availability/description, full-run skip instructions, seeded sample,
  checksum, and real-mode error.
- Focused LLMRouterBench differential test: 1 passed.
- Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff, and
  `git diff --check`: passed.
- Full Python regression: 1,768 passed, 6 skipped; 92.09% line (6,599/7,166),
  87.04% branch (1,833/2,106), and 90.94% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for this slice awaits the next RC push. TASK-027 Rust
  workspace and Python/Rust compatibility pass on Linux, Windows, and macOS;
  security/website pass. Its mutation and general Python workflows are finishing;
  the enforced context-band gate remains unchanged at 0.6667 < 0.90.

## Scope limits

Downloading/running the external benchmark repository and supplying commercial
model-to-registry mappings remain user-run steps exactly as documented by the
Python adapter.
