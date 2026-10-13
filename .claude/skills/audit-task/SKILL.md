---
name: audit-task
description: Independent audit of a completed or in-progress AgentRouter OS change. Use when the user asks to "audit", "review", or verify a task before release. Runs read-only reviewers and reproduces evidence; does not implement fixes.
context: fork
---

# Audit Task

Run an independent audit that trusts nothing without reproduced evidence.

1. Identify the change (task dir or `git diff`). Read the acceptance criteria.
2. Fan out READ-ONLY reviewers in parallel:
   - `verification-engineer` — correctness, negative paths, regression.
   - `security-reviewer-arros` — if execution/plugins/secrets/URLs touched.
   - `customer-advocate` — if customer-facing.
   - `product-architect` — if structural/compat.
3. Reproduce each claimed result with the exact command. Old checkboxes are not
   evidence.
4. Classify findings CRITICAL/HIGH/MEDIUM/LOW/INFO and write to the task's
   `audit.md` (+ `loop/reports/audit-<date>/` for whole-product audits).
5. Do NOT edit source here — hand findings to the repair loop.
