# TASK-157 — Public default grading runtime

Build the remaining Rust equivalent of Python's default public
`grade(cases, classify_fn=None, measure_all=False, context_report=None)` path.
It must discover packaged seed models and the actual shipped CLI command surface
without caller-provided manifests, and expose classification-only and all-
dimension entrypoints that preserve the current report contract.

Test absent/default classifier behavior, empty and populated cases, both
measurement modes, real command/group discovery, model loading failures, and
report fields. Keep grading and platform module rows Partial until every public
Python behavior is measured.
