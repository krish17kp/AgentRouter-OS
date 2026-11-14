# TASK-146 evidence

The mutation job at `0d3ea70` reports ten unreviewed survivors in the
TASK-144 response-status condition. Its numeric scores pass, but its explicit
survivor-review requirement fails. The workflow's test selection includes
`tests/test_openai_adapter.py` and excludes the Rust bridge differential, so
direct status cases were added to the selected test file.

The test covers valid statuses 200 and 299 plus 199, 300, 302, 399, 400, 429,
500, and 599. After formatting, the combined OpenAI adapter selection passes
78 tests; Ruff check and formatting also pass. Hosted mutation validation has
not yet run with the new tests. No thresholds, survivor allowlists, or release
gates were changed.

## Addendum — latest hosted campaign at `0d0a662`

The latest critical mutation campaign passes the unchanged numeric thresholds
but reports one unreviewed survivor:
`agentrouter.openai_adapter.x_run_text_response__mutmut_65`. Its exact diff
removes the fallback argument from `getattr(response, "status", None)`. A
response without a status can then raise an uncaught `AttributeError` or bypass
the status check. The adapter now rejects absent and malformed status values
with a stable `OpenAIAdapterError`; regression coverage checks absent, null,
boolean, float, and string statuses. The adapter module selection passes 60
tests locally, Ruff passes, and the exact hosted mutant is killed by the local
mutmut 3.6.0 run. The complete hosted mutation campaign awaits the next RC
push. The release gate independently remains failed at the unchanged frozen
context-band result 0.6667 < 0.90. The full Python suite passes 2,570 tests
with 5 skips locally; fresh coverage percentages are being measured separately.

## Addendum — hosted repair and refreshed coverage

The fix was pushed in `db2c67d`. Hosted critical mutation run `43618274518`
passes all selected-result and survivor-review gates: 1,706 mutants, 0.9701
overall, 0.9674 safety/policy/execution, 0.9815 routing, and zero unreviewed
survivors. The full Linux/Python 3.12 suite passes 2,570 tests with 5 skips.
Coverage is 92.030% statements, 87.712% branches, and 91.038% combined in
[`docs/COVERAGE_REPORT_2026-11-14-TASK-147.md`](../../../docs/COVERAGE_REPORT_2026-11-14-TASK-147.md).
The later `c1b6750` evidence-only push repeats the passing result in hosted run
`43619491827`, with 1,706 mutants, 0.9701 overall, 0.9674
safety/policy/execution, 0.9815 routing, and zero unreviewed survivors. The
separate enforcing release gate still fails at frozen context-band accuracy
0.6667 against the unchanged 0.90 threshold.
