"""Deterministic load, concurrency, soak and failure-injection lab (TASK-018B).

This package exists to find reliability defects, not to produce a benchmark
number. The distinction matters for how it is used in CI: correctness invariants
(no unexpected 5xx, no lost writes, no request-id bleed) are gated, while timing
is recorded and reported but never asserted — shared CI runners cannot support a
stable wall-clock threshold, and a flaky gate teaches people to ignore it.
"""

from .harness import (
    LoadOutcome,
    LoadSpec,
    RunningApp,
    run_load,
    serve_app,
)

__all__ = ["LoadOutcome", "LoadSpec", "RunningApp", "run_load", "serve_app"]
