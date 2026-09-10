# TASK-010 test contract

- A complete killed campaign passes.
- An unreviewed survivor fails even if the numeric score would pass.
- An allowlisted survivor remains visible and still counts against the score.
- no-tests, unchecked, suspicious, and segfault results fail completeness.
- A missing execution function selection fails completeness.
- Invalid or missing tool output exits as tool failure, not a passing score.
- Workflow YAML parses and the runner has an inner timeout below the job timeout.
- Final acceptance requires the GitHub artifact from a real Ubuntu run.
