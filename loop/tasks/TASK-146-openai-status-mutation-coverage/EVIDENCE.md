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
