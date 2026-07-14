"""Performance evaluator (§7 performance, weight 5).

A smoke perf check, not a benchmark. Times classify + full route over N sample
tasks with ``time.perf_counter`` and compares the median against documented
thresholds tuned for a developer laptop. Score is 1.0 while both medians are
under threshold and degrades linearly (never below 0) as they exceed it.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Sequence

from ...classifier import classify
from ...engine import route
from ...schema import ModelEntry

# Documented thresholds (milliseconds, median). Generous smoke-test ceilings.
CLASSIFY_THRESHOLD_MS = 50.0
ROUTE_THRESHOLD_MS = 100.0

_SAMPLE_TASKS = (
    "Refactor the payment module and add unit tests",
    "Write a blog post about our API launch",
    "Summarize this 30k token incident report",
    "Design a scalable multi-tenant architecture",
    "Fix the off-by-one bug in the pagination helper",
    "Analyze the query plan and recommend indexes",
    "Rotate the production API keys and update secrets",
    "Draft release notes for version 2.1",
)


def _median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000, 3) if samples else 0.0


def _degrade(median_ms: float, threshold_ms: float) -> float:
    """1.0 at/under threshold; linear decay to 0.0 at 2x threshold."""
    if median_ms <= threshold_ms:
        return 1.0
    over = (median_ms - threshold_ms) / threshold_ms
    return max(0.0, 1.0 - over)


def evaluate_performance(
    models: Sequence[ModelEntry] | None = None,
    tasks: Sequence[str] = _SAMPLE_TASKS,
    classify_fn=classify,
) -> dict:
    """Score routing-pipeline latency against documented median thresholds."""
    if models is None:
        from . import load_seed_models

        models = load_seed_models()
    models = list(models)

    classify_times: list[float] = []
    route_times: list[float] = []
    for task in tasks:
        t0 = time.perf_counter()
        cls = classify_fn(task)
        t1 = time.perf_counter()
        route(models, cls)
        t2 = time.perf_counter()
        classify_times.append(t1 - t0)
        route_times.append(t2 - t1)

    classify_median = _median_ms(classify_times)
    route_median = _median_ms(route_times)
    score = min(
        _degrade(classify_median, CLASSIFY_THRESHOLD_MS),
        _degrade(route_median, ROUTE_THRESHOLD_MS),
    )
    return {
        "score": round(score, 4),
        "detail": {
            "n_samples": len(tasks),
            "classify_median_ms": classify_median,
            "route_median_ms": route_median,
            "classify_threshold_ms": CLASSIFY_THRESHOLD_MS,
            "route_threshold_ms": ROUTE_THRESHOLD_MS,
            "note": "smoke perf check on this machine; not a benchmark",
        },
    }
