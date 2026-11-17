# TASK-257 — CLI compatibility recheck

## Evidence

- The complete Rust/Python and Rust CLI compatibility selection passes 893
  tests with 1 expected skip.
- The only warning is the existing non-failing Starlette/httpx deprecation.
- The canonical release gate remains `release_ready=false` solely because
  `context_band_accuracy` is `0.6667 < 0.90`.
