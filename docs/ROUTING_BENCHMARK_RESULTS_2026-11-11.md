# Routing latency benchmark — 2026-11-11

## Method

Reproduce both implementations with the same synthetic fleet sizes and 100-call
warm-up:

```console
PYTHONPATH=. python scripts/benchmark_routing_latency.py --iterations 2000
cargo run --release --locked -p agentrouter-routing --bin routing_bench -- --iterations 2000
```

The benchmark measures only the pure in-process Python filtering and ranking
pass using deterministic synthetic candidate fleets. It warms up for 100 calls,
then times 2,000 routes per fleet. It excludes classification, registry and
SQLite work, network calls, model execution, and OpenAI/provider latency. These
numbers are a local baseline, not end-to-end or production service latency.

Environment: Python 3.12.15; Linux 7.0.0-43-generic; x86_64; glibc 2.43.

## Initial Python baseline

| Candidates | Iterations | p50 (µs) | p95 (µs) | Routes/s |
|---:|---:|---:|---:|---:|
| 10 | 2,000 | 31.15 | 34.54 | 31,624.64 |
| 100 | 2,000 | 292.62 | 319.43 | 3,382.60 |
| 1,000 | 2,000 | 3,427.17 | 3,776.61 | 284.78 |

Re-run on target hardware and with realistic registry sizes before using this
baseline for capacity or latency commitments. Rust and Python numbers should
only be compared under the same workload, host, warm-up, and timing method.


## Paired Python/Rust sample

A later sequential run on the same machine used the same candidate generation,
filtering/scoring workload, 100 warm-up calls, and 2,000 measured routes per
fleet. Rust was built with `--release`; Python used CPython 3.12.15. The two
programs use their standard monotonic clocks, so sub-microsecond timing overhead
is not identical. These values are a local sample, not a service-level claim.

Environment: CPython 3.12.15; rustc 1.99.0; Linux 7.0.0-43-generic;
x86_64; glibc 2.43.

| Candidates | Language/build | p50 (µs) | p95 (µs) | Routes/s | p50 ratio vs Python |
|---:|---|---:|---:|---:|---:|
| 10 | Python | 54.88 | 81.71 | 16,927.17 | 1.00× |
| 10 | Rust release | 20.36 | 31.53 | 45,176.82 | 2.70× |
| 100 | Python | 503.85 | 674.00 | 1,866.36 | 1.00× |
| 100 | Rust release | 155.14 | 167.83 | 6,412.07 | 3.25× |
| 1,000 | Python | 5,156.30 | 5,612.76 | 186.81 | 1.00× |
| 1,000 | Rust release | 1,616.70 | 1,679.03 | 618.06 | 3.19× |

The earlier Python-only baseline above remains a separate run; its lower values
show why one local timing sample should not be treated as a latency guarantee.
The paired result measures filtering and ranking only: it excludes model
classification, registry loading, SQLite, network calls, provider latency, and
execution. It also does not establish routing-quality improvement; the existing
Python/Rust differential tests establish output compatibility for their tested
cases.
