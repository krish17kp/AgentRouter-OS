"""Reproducible local CPU benchmark for the pure Python routing pass.

This excludes classification, registry loading, SQLite, network/provider time,
and model execution. Results describe only in-process filtering and ranking of
synthetic candidate fleets; they are not production latency claims.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

from agentrouter.engine import route
from agentrouter.schema import (
    Ability,
    ApprovalLevel,
    Classification,
    ContextBand,
    DeprecationStatus,
    LatencyTier,
    Level,
    ModelEntry,
    OutputType,
    PricingTier,
    TaskType,
)


def fleet(size: int) -> list[ModelEntry]:
    tiers = list(PricingTier)
    latencies = list(LatencyTier)
    return [
        ModelEntry(
            provider=f"provider-{index % 8}",
            model_id=f"synthetic-model-{index:05d}",
            context_window=(16_000, 64_000, 256_000)[index % 3],
            max_output_tokens=8_000,
            pricing_tier=tiers[index % len(tiers)],
            latency_tier=latencies[index % len(latencies)],
            ability=Ability(
                coding=(index * 7 % 11),
                reasoning=(index * 5 % 11),
                writing=(index * 3 % 11),
            ),
            tool_support=["file-edit"] if index % 5 != 0 else [],
            vision_support=index % 7 == 0,
            deprecation_status=DeprecationStatus.active,
        )
        for index in range(size)
    ]


def classification() -> Classification:
    return Classification(
        task_type=TaskType.coding,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=12_000,
        context_band=ContextBand.small,
        output_type=OutputType.code,
        tool_needs=["file-edit"],
        approval_level=ApprovalLevel.auto,
    )


def measure(size: int, iterations: int) -> dict[str, int | float]:
    models = fleet(size)
    cls = classification()
    for _ in range(min(100, iterations)):
        route(models, cls)

    samples_ns: list[int] = []
    started = time.perf_counter()
    for _ in range(iterations):
        sample_started = time.perf_counter_ns()
        route(models, cls)
        samples_ns.append(time.perf_counter_ns() - sample_started)
    elapsed = time.perf_counter() - started
    ordered = sorted(samples_ns)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "candidate_models": size,
        "iterations": iterations,
        "p50_us": round(statistics.median(ordered) / 1_000, 2),
        "p95_us": round(ordered[p95_index] / 1_000, 2),
        "routes_per_second": round(iterations / elapsed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--fleets", type=int, nargs="+", default=[10, 100, 1_000])
    args = parser.parse_args()
    if args.iterations < 1 or any(size < 1 for size in args.fleets):
        parser.error("iterations and fleet sizes must be positive")
    print(
        json.dumps(
            {
                "benchmark": "python-pure-routing-v1",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "warmup_iterations": min(100, args.iterations),
                "results": [measure(size, args.iterations) for size in args.fleets],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
