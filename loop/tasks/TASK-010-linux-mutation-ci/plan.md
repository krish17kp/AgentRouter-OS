# TASK-010 plan

1. Pin mutmut 3.6.0 and configure only the critical routing, safety, limits, host,
   and execution-gateway surfaces with their focused tests.
2. Run the campaign through a repository-owned wrapper with separate exit codes
   for score failure and tool/environment failure.
3. Parse mutmut metadata without trusting console text; reject missing, skipped,
   unchecked, suspicious, interrupted, or crashed selected mutants.
4. Gate overall score at 0.85 and safety/policy/execution at 0.95. Require every
   survivor to have an exact, reviewed non-bypass rationale.
5. Upload JSON, Markdown, survivor list, tool status, and raw log from GitHub Linux.
6. Inspect survivors, add important regression tests, rerun, and record the real score.

Rollback: remove the standalone workflow/configuration and parser. It does not alter
runtime behavior or external infrastructure.
