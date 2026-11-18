# TASK-026 — Rust LongBench v2 row normalization parity

## Contract covered

Ported LongBench v2's reporting bucket boundaries, context word-count estimate
(`int(words * 1.3)`), small/medium/large context-band labels, source IDs and
metadata, question deduplication, and normalized-task deduplication. Preserves
the Python distinction between a missing `_id` (row index) and explicit null,
and between a missing domain (empty string label, `None` note) and explicit null.

## Differential evidence

- Raw fixture compares normalized cases and bucket results at negative, exact,
  and adjacent thresholds from 8k through 512k and the upper fallback.
- Focused LongBench differential test: 1 passed.
- Rust workspace, Clippy (`-D warnings`), rustfmt, Ruff, and `git diff --check`:
  passed.
- Full Python regression: 1,766 passed, 6 skipped; 91.95% line (6,589/7,166),
  86.85% branch (1,829/2,106), and 90.79% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for this slice awaits the next RC push. TASK-025 Rust
  workspace/compatibility passed on Linux, Windows, and macOS; security, website,
  and mutation passed. General CI's only failure remains the frozen context-band
  gate (0.6667 < 0.90).

## Scope limits

Downloading the Hugging Face data and running a long-context model remain
external-runtime work; the port covers adapter row preparation and bucketing.
