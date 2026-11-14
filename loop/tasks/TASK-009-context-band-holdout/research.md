# TASK-009 research and leakage record

The final holdout was checksum-locked before classifier scoring at
`ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f`.
It has 45 cases balanced 15/15/15 across small, medium, and large, while the
development split has 24 separate cases. Before scoring, automated comparison found
zero exact or near matches against development prompts, 165 gold prompts, and Python
test string literals (SequenceMatcher >= 0.88 or token Jaccard >= 0.82).

The pre-TASK-004 comparator is a literal local copy of the historical token/context
rules. It does not import live classifier matchers or band thresholds. Tests pin its
holdout accuracy, macro-F1, and per-band recall.

After the first frozen score exposed weak generalization, one classifier revision was
designed only from the development split: portable explicit scale units, conceptual
question detection, and existing-artifact cues. It reached 24/24 development cases and
was frozen before the post-change holdout run. No further changes were made from final
holdout failures.
