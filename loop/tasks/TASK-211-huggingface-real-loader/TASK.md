# TASK-211 — Bounded Hugging Face real-data loader

## Objective

Advance the Rust evaluation migration beyond fixture-only behavior by adding
an explicit, bounded loader for public Hugging Face dataset rows while
preserving offline safety and the no-fixture-fallback invariant.

## Acceptance

- CLINC150, Banking77, MASSIVE, LongBench v2, and SWE-bench metadata rows use
  the existing Rust normalizers;
- network loading is opt-in through `AGENTROUTER_ENABLE_HF_REAL=1`;
- redirects are refused, phase timeouts are bounded, response and row limits
  are enforced, and malformed rows fail closed;
- default offline status/preparation remains external and does not download;
- local transport tests cover valid rows and malformed row rejection;
- at least one public dataset is exercised end-to-end without fixture
  fallback;
- LLMRouterBench/TwinRouterBench, Docker/model full runs, and human
  annotation remain explicitly outside this slice.
