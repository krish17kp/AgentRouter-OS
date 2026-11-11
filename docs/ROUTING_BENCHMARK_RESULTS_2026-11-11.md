# Routing latency benchmark — 2026-11-11

## Method

Run with:

```console
.venv/bin/python scripts/benchmark_routing_latency.py --iterations 2000
```

The benchmark measures only the pure in-process Python filtering and ranking
pass using deterministic synthetic candidate fleets. It warms up for 100 calls,
then times 2,000 routes per fleet. It excludes classification, registry and
SQLite work, network calls, model execution, and OpenAI/provider latency. These
numbers are a local baseline, not end-to-end or production service latency.

Environment: Python 3.12.15; Linux 7.0.0-43-generic; x86_64; glibc 2.43.

## Results

| Candidates | Iterations | p50 (µs) | p95 (µs) | Routes/s |
|---:|---:|---:|---:|---:|
| 10 | 2,000 | 31.15 | 34.54 | 31,624.64 |
| 100 | 2,000 | 292.62 | 319.43 | 3,382.60 |
| 1,000 | 2,000 | 3,427.17 | 3,776.61 | 284.78 |

Re-run on target hardware and with realistic registry sizes before using this
baseline for capacity or latency commitments. Rust and Python numbers should
only be compared under the same workload, host, warm-up, and timing method.
