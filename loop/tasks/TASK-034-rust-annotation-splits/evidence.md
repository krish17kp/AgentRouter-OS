# TASK-034 — Rust annotation dataset partitioning

## Contract covered

Ported deterministic train/dev/private-holdout partitioning. Prompt duplicate
clusters remain together; the smallest normalized prompt is the stable cluster
key; SHA-256 modulo assignment and configurable split ratios match Python; each
split is ordered by item ID. Dev and private holdout are checked against the
provided frozen-holdout prompts, and a leak fails closed with the Python error
message.

## Differential evidence

- Exact Python/Rust output comparison covers default and custom ratios,
  duplicate-cluster grouping, item ordering, and split metadata.
- A deliberate exact frozen-holdout overlap is rejected with the matching
  Python `LeakageError` message.
- Focused differential, Rust workspace, Clippy, format, Ruff, and diff checks
  pass locally. Cross-platform workflow evidence follows the push.
- Only prompt text is read by the leakage guard; frozen labels are not used.
