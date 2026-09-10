# TASK-009 plan

1. Author distinct development and final-holdout sets without running the classifier.
2. Validate schema/category/band balance and eliminate exact/near leakage against development,
   current gold prompts, and hard-coded test prompt literals.
3. Lock the final-holdout file checksum before the first scoring run.
4. Add deterministic metrics (accuracy, macro-F1, per-band recall, Wilson intervals, bootstrap
   macro-F1 interval) and a frozen pre-TASK-004 reference implementation.
5. Make the existing `context_band_accuracy>=0.90` release gate use final-holdout accuracy during
   `eval run --all`; leave the other six names and thresholds byte-for-byte unchanged.
6. Record the first result without modifying classifier heuristics, then run regression/review.

