# TASK-250 — Prompt configuration parity

## Objective

Match Python's task-based prompt generation configuration semantics.

## Evidence

- Rust task prompt generation now consumes configured routing weights while
  preserving Python's behavior of not applying the route policy cap in this
  prompt-only path.
- A differential regression covers a weighted config with a restrictive
  `max_pricing_tier`; Python and Rust prompt output match.
- The focused decision/unified CLI selection passes 44 tests; strict Clippy,
  formatting, and diff checks pass.
