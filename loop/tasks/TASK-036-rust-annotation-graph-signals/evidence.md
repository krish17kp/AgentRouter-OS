# TASK-036 — Rust annotation graph impact signal

## Contract covered

Added the Rust counterpart for Graphify graph loading, node-name and file-stem
extraction, ASCII prompt token matching, direct-neighbor reach, the bounded
impact feature, and the default `graphify-out/graph.json` path.

## Differential evidence

- Three Python/Rust cases pass for absent and invalid-JSON fallback, node fields
  and file stems, duplicate edges, match/miss behavior, empty/falsey edge
  fallback to `links`, and feature saturation behavior.
- `cargo test --workspace --locked`, evaluation crate tests, Clippy, Rust
  format, Ruff, and the focused three-case compatibility suite pass locally.
- This module remains **Partial**. Python memoizes four paths with an LRU and
  raises for malformed root/node shapes; the Rust probe currently reloads and
  safely falls back/ignores those malformed shapes.

The signal remains advisory and opt-in; absent graph data produces a zero
feature and does not manufacture an impact score.
