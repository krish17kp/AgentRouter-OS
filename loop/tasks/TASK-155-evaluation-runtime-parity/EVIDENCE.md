# TASK-155 evidence

Baseline at `2542e2d`: when a caller supplied a context-band generalization
object without a valid `current_holdout.accuracy`, Rust silently substituted
ordinary classification context accuracy. Python raised instead.

Rust grading now returns a typed failure path and every runner/probe propagates
it. Missing reports retain the ordinary classification fallback; explicit JSON
null matches Python None; numeric and boolean accuracy values match Python; and
missing, nested-null, null-valued, and string-valued accuracy inputs fail.

Focused Python/Rust differential passes 6 cases; all 40 evaluation compatibility
tests, the full Rust workspace, and strict Clippy pass. Independent review found
and verified the explicit-null repair. Full Python regression passes 2,609/7 in
437.64 seconds at 92.021% statement, 87.833% branch, and 91.058% combined
coverage. No threshold or frozen input changed.
