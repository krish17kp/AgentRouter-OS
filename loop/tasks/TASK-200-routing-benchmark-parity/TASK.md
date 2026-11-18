# TASK-200 — Routing benchmark parity

## Objective

Re-run the Python and optimized Rust pure-routing benchmarks with the same
synthetic fleets and iteration count, then record the comparison without
turning local CPU timing into a production guarantee.

## Acceptance

- both implementations use 10, 100, and 1,000 candidate fleets;
- both run 2,000 measured iterations with a 100-iteration warmup;
- p50 and p95 results are recorded with runtime/platform context;
- no network, provider, registry, SQLite, or model-execution time is included.
