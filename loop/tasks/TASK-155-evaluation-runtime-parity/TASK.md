# TASK-155 — Fail-closed supplied holdout grading

Prioritize supplied holdout report validation: Rust currently falls back to ordinary
classification accuracy if current_holdout.accuracy is missing or malformed. Fail
closed, preserving gate thresholds and frozen datasets. Compare Python failures.

Acceptance requires valid numeric and boolean accuracies to match Python, JSON
null to behave as Python None, and missing, null-valued, or string-valued nested
accuracy to return an error. Every Rust runner and probe must propagate that error.
No gate threshold or frozen input changes.
