# Critical module mutation report — 2026-11-14

The full Linux critical-module mutation campaign for TASK-114 passed with
`mutmut` 3.6.0 and pytest 9.0.3.

| Group | Score | Required | Mutants | Reviewed survivors | Result |
|---|---:|---:|---:|---:|---|
| Safety, policy, and execution | 0.9670 | 0.95 | 1,362 | 45 | Pass |
| Routing and engine | 0.9815 | 0.85 | 324 | 6 | Pass |
| **Overall** | **0.9698** | **0.85** | **1,686** | **51** | **Pass** |

The campaign completed all selected results: 1,635 mutants were killed and 51
survived with reviewed equivalence rationales. There are zero unreviewed
survivors and no incomplete results. The exact campaign selection is configured
in `pyproject.toml`; every survivor rationale is recorded in
`mutation-survivor-allowlist.json`. The report-only gate passed all five checks:
overall score, complete results, reviewed survivors, safety/policy/execution,
and routing.

Command: `scripts/run_mutation_ci.py --timeout-seconds 2100 --max-children 4`.
