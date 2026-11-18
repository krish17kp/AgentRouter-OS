# TASK-025 — Rust MASSIVE locale normalization parity

## Contract covered

Ported the MASSIVE raw-row transformation across English, Hindi, and French
locale batches. It preserves language-specific identifiers and provenance,
per-locale lowercased deduplication, the shared normalized-task deduplication,
scenario/intent string conversion (including missing versus explicit null),
fixture language selection, and Python's unsupported-locale error. Unknown row
fields are ignored as Python does.

## Differential evidence

- Three language-selection fixtures (all defaults, reordered subset, single
  language) plus an unsupported-language fixture cover all supported locales,
  row indexes, global deduplication, null/missing values, and source metadata.
- Focused MASSIVE, Banking77, CLINC150, and shared adapter-base tests: 14 passed.
- Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff check/format, and
  `git diff --check`: passed.
- Full Python regression: 1,765 passed, 6 skipped; 91.75% line (6,575/7,166),
  86.61% branch (1,824/2,106), and 90.58% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for this slice is pending the next RC push. TASK-024 Rust
  workspace and non-skipping compatibility passed on Linux/Windows/macOS, and
  security/site/mutation passed. The only general CI failure is the unchanged
  frozen context-band gate at 0.6667 < 0.90.

## Scope limits

Hugging Face downloads and adapter runtime wiring remain Python-only; Rust
normalizes caller-supplied locale records.
