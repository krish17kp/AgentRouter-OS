# TASK-156 — Consistent injected evaluation grading

Close the classifier-consistency gap in Rust's measured scorecard. A caller-
supplied classifier must drive classification, routing, safety, and performance
instead of the scorecard silently mixing it with the default classifier.

Test default and injected classifiers across all four dependent dimensions and
preserve the default scorecard behavior. This slice does not claim complete
public `grade(...)` parity, live CLI discovery, or full grading/platform module
parity; those remain the next runtime task. Adapter base/runner remain Partial
for external loader lifecycle and provenance.
