# TASK-009 test contract

- Development and holdout IDs/prompts are unique and all small/medium/large bands appear.
- Coding, review, audit, refactor, documentation, analysis, summarization, data-pipeline, and
  ambiguous categories appear in the final holdout.
- Final holdout checksum is immutable absent an explicit version bump.
- No exact or near-identical holdout prompt exists in development, gold, or Python test literals.
- Metrics are deterministic, bounded, and include intervals and per-band recall.
- Pre-change/current comparison uses the same frozen holdout.
- `eval run --all` sources the context gate from the holdout and preserves the six other gates.

