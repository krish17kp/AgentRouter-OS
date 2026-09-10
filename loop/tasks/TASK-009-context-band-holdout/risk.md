# TASK-009 risk review

The main risk is benchmark gaming: authoring or editing final cases after observing predictions,
copying gold/test wording, or weakening the 0.90 threshold. The final file is scored only after
leakage validation and checksum locking; classifier heuristics are out of scope for this task after
that first score. The public model-assisted holdout is a stronger generalization check but is not a
substitute for a private, independently human-reviewed set.

