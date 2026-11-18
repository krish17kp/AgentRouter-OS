# TASK-024 — Rust Banking77 normalization parity

## Contract covered

Ported conversion of caller-supplied PolyAI/Banking77 test rows into normalized
AgentRouter cases: trimmed query text, label tags, banking domain, expected
informational task families and low risk, dataset/license provenance, row IDs,
notes, checksums, and Python-compatible exact/normalized duplicate removal.
Remote dataset fetching remains external-runtime-only.

## Differential evidence

- Two raw-row fixtures cover customer-query normalization, duplicate and
  punctuation-insensitive duplicate removal, source row indices, label tags,
  low-risk calibration, and provenance.
- Focused Banking77, CLINC150, and shared adapter-base tests: 10 passed.
- Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff check/format, and
  `git diff --check`: passed.
- Full Python regression: 1,761 passed, 6 skipped; 91.52% line (6,558/7,166),
  86.23% branch (1,816/2,106), and 90.31% combined coverage (Python 3.12.15,
  Linux).
- Cross-platform CI for Banking77 awaits the next RC push. TASK-023's Rust
  workspace/compatibility CI passed on Linux, Windows, and macOS; general CI
  and mutation checks are still running. The frozen release gate remains
  unchanged at 0.6667 < 0.90.

## Scope limits

Hugging Face downloading and the `datasets` runtime are not ported. Rust accepts
raw records as input and is tested against Python's real-row normalizer.
