---
name: customer-review
description: Review an AgentRouter OS feature as a first-time and everyday customer. Use for any customer-facing change (CLI, help text, errors, install, docs). Tests the scenarios in loop/PRODUCT_SCENARIOS.yaml from the packaged artifact.
context: fork
---

# Customer Review

Delegate to `customer-advocate`. For each scenario in
`loop/PRODUCT_SCENARIOS.yaml`:

1. Run the scenario's steps against the packaged CLI/server (prefer the wheel).
2. Check: 5-minute first route, actionable errors, accurate examples/docs,
   no unexplained jargon, NO_COLOR accessibility, Windows + Linux instructions,
   clean uninstall/rollback, clear privacy + cost behavior.
3. Record PASS/FAIL per scenario with the exact command in the task's
   `customer-review.md`.

A technically correct but confusing feature is NOT complete.
