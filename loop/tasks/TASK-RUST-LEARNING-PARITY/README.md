# Rust feedback learning parity

Date: 2026-11-11

## Scope

Move `agentrouter.learning.learned_weights` into a dedicated
`agentrouter-learning` Rust crate. Keep weight adaptation deterministic and
reversible: the Rust helper recomputes from the feedback table on each route,
uses the same three-rating minimum, negative threshold, per-rating step, total
shift cap, and minimum cost weight, and emits the same explanation text.
Four-decimal weight rounding uses the shared Python-compatible ties-to-even
helper from `agentrouter-routing`.

The route CLI now delegates its existing learning path to this crate. The
fixture-only `learning_from_json` executable creates an in-memory feedback
table; it has no network or file access.

## Evidence

- Three Rust unit tests cover minimum sample, positive feedback, negative
  adjustment, saturation, null ratings, and the minimum cost bound.
- Nine Python/Rust differential cases compare full weights and explanation
  strings, including a decimal ties-to-even edge case.
- Existing CLI cross-language route tests continue to cover the learning
  enabled and disabled configuration behavior.

## Limits

This ports the bounded feedback-weight function only. Learned-model training
and activation remain controlled by the separate frozen context-band
evaluation and are still disabled in default routing.
