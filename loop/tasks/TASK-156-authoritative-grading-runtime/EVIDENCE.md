# TASK-156 evidence

Baseline: run_all_dimensions used the default classifier for every dimension,
even where callers needed a single injected classifier evaluated consistently.

run_all_dimensions_with and run_classification_with now propagate one
classifier callback through classification, routing, safety, and performance.
Default wrappers retain the original classifier. The injected differential uses a
prediction that differs from default behavior and passes 42 scorecard/evaluation
compatibility tests. Rust evaluation tests, strict Clippy, independent review, and
full Python 2,610/7 at 92.021% statement, 87.833% branch, and 91.058% combined
coverage pass.

The grading/platform rows remain Partial. TASK-157 owns public default grading,
actual CLI-surface discovery, and model discovery parity.
