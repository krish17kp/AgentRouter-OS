# TASK-222 — Python-compatible bundle timestamps

## Objective

Align the Rust diagnostic bundle's generated timestamp with Python's stable
UTC ISO-8601 representation without changing the bundle's redaction or privacy
boundary.

## Acceptance

- `generated_at` uses UTC, six fractional digits, and an explicit `+00:00`
  offset;
- Rust and Python/Rust bundle checks remain green;
- strict Clippy and focused bundle tests pass.
