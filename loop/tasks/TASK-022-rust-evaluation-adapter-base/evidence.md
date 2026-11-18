# TASK-022 — Rust evaluation fixture adapter base

## Contract covered

Added reusable Rust methods matching fixture-backed `DatasetAdapter` behavior:
metadata serialization, fixture availability, JSONL parsing with blank-line
handling, case checksums, duplicate-ID/task and metadata validation,
deterministic sampling, adapter description, and explicit `SKIPPED_EXTERNAL`
for real mode when the optional Hugging Face `datasets` runtime is unavailable.

## Differential evidence

- Six adapter fixtures: CLINC150, Banking77, MASSIVE, LongBench v2, SWE-bench,
  and TwinRouterBench.
- Compares metadata, fixture availability, real availability/reason,
  `describe()`, all normalized records, deterministic seeded samples, aggregate
  checksums, and real-mode error messages.
- Python/Rust focused evaluation adapter + gold adapter tests: 12 passed.
- Full Rust workspace tests, Clippy (`-D warnings`), rustfmt, Ruff check/format:
  passed.
- Full Python suite: 1,757 passed, 6 skipped; 91.24% line, 85.80% branch,
  90.00% combined coverage (Python 3.12.15, Linux).
- Cross-platform CI: pending the next authorized RC push.

## Scope limits

Real downloads, adapter-specific transformations over remote rows, dataset
preparation, and evaluation runners/CLI remain Python-only. This slice never
falls back from real mode to a fixture.
