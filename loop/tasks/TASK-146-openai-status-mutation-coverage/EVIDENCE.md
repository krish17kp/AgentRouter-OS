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
