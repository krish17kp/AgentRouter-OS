# Routing benchmark results — 2026-11-11

## Reproduction

```console
.venv/bin/python -m pytest tests/test_routing_benchmark.py -q
```

The fixture-level routing gold check is also reproducible with:

```python
from pathlib import Path
import agentrouter
from agentrouter.evaluate import evaluate_routing

path = Path(agentrouter.__file__).parent / "benchmarks" / "routing_gold_v1.yaml"
print(evaluate_routing(path))
```

## Result

| Measure | Result |
|---|---:|
| Routing gold scenarios | 12 / 12 passed (100%) |
| Focused routing benchmark and invariant tests | 15 passed |
| Scenario failures | 0 |
| Measured latency or token cost | Not measured |

The 12 scenarios cover context-window exclusions, required tools, vision support,
ability ranking, declared fallback, price-tier caps, deprecated/retired model
behavior, no-eligible outcomes, cost fit, and cross-provider fallback. The
additional tests check monotonic safety and eligibility properties. These are
contract and decision-quality checks over checked-in fixtures, not live model
quality, provider reliability, latency, throughput, or pricing measurements.

## Interpretation

The current routing implementation satisfies every committed gold scenario and
all 15 focused benchmark/invariant tests. No scoring weights were changed from
this result. Any production routing optimization should add a before/after
benchmark, held-out tasks, and measured outcomes before it changes ranking.
