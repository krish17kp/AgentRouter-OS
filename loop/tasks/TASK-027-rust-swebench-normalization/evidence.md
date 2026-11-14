# TASK-027 — Rust SWE-bench Lite row preparation parity

## Contract covered

Ported preparation of caller-supplied SWE-bench Lite issue rows for AgentRouter
classification/routing: whitespace trim, empty/exact/normalized duplicate
removal, row-based fallback IDs, explicit-null IDs, repository tags, coding
expectations, minimum coding ability 7, dataset-native provenance, and notes.
Unknown dataset row fields are ignored. Docker issue solving remains separate.

## Differential evidence

- Raw fixture covers empty rows, exact and punctuation-normalized duplicates,
  fallback and explicit-null IDs, missing/null repository metadata, routing
  ability, provenance, and checksums.
- Focused SWE-bench and LongBench differential tests: 2 passed.
- Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff, and
  `git diff --check`: passed.
- Full Python regression: 1,767 passed, 6 skipped; 92.09% line (6,599/7,166),
  87.04% branch (1,833/2,106), and 90.94% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for SWE-bench awaits the next RC push. TASK-026 Rust
  workspace passed Linux/Windows/macOS; Rust compatibility passed Linux/macOS,
  with Windows still running. Security passed; the general release gate remains
  frozen at 0.6667 < 0.90.

## Scope limits

Hugging Face fetching and Docker-based issue solving are not ported. Rust
normalizes caller-supplied rows for classification and routing evaluation.
