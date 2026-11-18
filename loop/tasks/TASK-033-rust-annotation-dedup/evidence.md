# TASK-033 — Rust annotation duplicate/leakage checks

## Contract covered

Ported annotation prompt normalization, three-word shingle Jaccard, Python
`SequenceMatcher` ratio (including its 200-character popularity heuristic),
combined near-duplicate similarity, transitive union-find clustering, and
ordered exact/near leakage reports with Python half-even score rounding.

## Differential evidence

- The differential fixture covers punctuation and case normalization,
  Unicode removal, exact/near matches, clustered prompt groups, ordered leakage
  reports, and strings long enough to exercise SequenceMatcher's autojunk rule.
- Focused Python/Rust differential test, Rust workspace, Clippy, format, Ruff,
  and diff checks pass locally.
- This code compares only prompt text and does not consume labels or tune the
  classifier on the frozen holdout.
