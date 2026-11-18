# TASK-023 — Rust CLINC150 normalization parity

## Contract covered

Ported ordered CLINC intent-substring mapping and normalization of caller-supplied
`clinc_oos` test rows: whitespace trimming, case-insensitive duplicate removal,
post-normalization task-hash deduplication, out-of-scope tagging, curated versus
needs-review labels, expected task-family sets, source/license provenance,
record IDs, notes, and checksums. The Rust implementation does not download
remote data; the existing Python fixture/offline path remains available.

## Differential evidence

- Two raw-row fixtures cover every curated mapping hint, default fallback,
  out-of-scope intent, row-index preservation, duplicate handling, and labels
  whose names contain overlapping mapping substrings.
- Focused CLINC150 plus shared adapter-base compatibility tests: 8 passed.
- Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff check/format, and
  `git diff --check`: passed.
- Full Python regression: 1,759 passed, 6 skipped; 91.50% line (6,557/7,166),
  86.18% branch (1,815/2,106), and 90.29% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for this new CLINC150 slice is pending its RC push. TASK-022
  Rust CI passed on Linux, Windows, and macOS, including non-skipping adapter
  compatibility. The general CI fails only at the enforced frozen context-band
  release gate (0.6667 < 0.90); live smoke is skipped without credentials.

## Scope limits

Hugging Face download behavior and `datasets` runtime are not ported. The Rust
normalizer accepts source records as input and is differential-tested against
the Python adapter's `_load_real` contract.
