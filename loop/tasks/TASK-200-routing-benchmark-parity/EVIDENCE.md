# TASK-200 evidence

Date: 2026-11-17

Commands:

```console
uv run --with '.[dev,server,security]' python scripts/benchmark_routing_latency.py \
  --iterations 2000 --fleets 10 100 1000
cargo run --release --locked -p agentrouter-routing --bin routing_bench
```

Environment: Linux x86_64, Python 3.12.15. Both runs use the pure routing
pass, synthetic candidates, 100 warmup iterations, and no I/O/provider time.

| Fleet | Python p50 / p95 (µs) | Rust p50 / p95 (µs) | Rust p50 ratio |
|---:|---:|---:|---:|
| 10 | 34.41 / 48.24 | 26.86 / 32.74 | 0.78× |
| 100 | 336.12 / 419.91 | 260.33 / 291.98 | 0.77× |
| 1,000 | 3560.56 / 4458.79 | 2244.93 / 2666.50 | 0.63× |

These are local comparative measurements, not production SLOs.
