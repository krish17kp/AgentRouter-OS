# TASK-044: Rust context-band evaluation parity

## Scope

Port `agentrouter/evaluation/context_bands.py` to the Rust evaluation crate,
without changing the development or frozen holdout datasets, reported model
results, or release threshold.

## Implementation

- Embedded the two packaged YAML datasets in the Rust crate; canonicalized
  line endings for the immutable holdout SHA-256 check and validated duplicate
  normalized prompts, IDs, context-band values, and required holdout categories.
- Ported Python lowercase/whitespace/punctuation normalization and
  `difflib.SequenceMatcher` similarity, including the default popular-item
  heuristic used for long prompts. Ported exact and near-duplicate split leak
  reporting while preserving reference order.
- Ported current scoring, the historical pre-TASK-004 comparator, Wilson
  confidence intervals, category/per-band confusion and recall, and the
  CPython-seeded 2,000-sample bootstrap interval.
- Added CLI probes and Python/Rust differential tests for the frozen end-to-end
  report, custom predictors, Unicode/long-text sequence similarity, and split
  leak findings.

## Evidence

- `.venv/bin/python -m pytest -q tests/test_rust_context_bands_compat.py`: 3
  passed locally.
- `cargo clippy -p agentrouter-evaluation --all-targets --all-features --locked
  -- -D warnings`: passed locally.
- The Rust report compared exactly against Python, including all holdout and
  development metrics and bootstrap intervals. The immutable holdout remains
  at 0.6667 accuracy and below the unchanged 0.90 gate pending independent
  human annotation.
- Linux/Windows/macOS hosted CI is required after the RC push.

## Release interpretation

The evaluator implementation is parity-complete. Its measurement still fails
the promotion threshold and must not be “fixed” by changing labels or gates.
Independent human annotation, OpenAI live validation, and production deploy
credentials remain under `Needs Krish`.
