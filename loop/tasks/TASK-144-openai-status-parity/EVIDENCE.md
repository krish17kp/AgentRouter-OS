# TASK-144 evidence

Python and Rust OpenAI adapters now require a 2xx response before parsing
content. The differential fixture checks 300, 302, and 399, and the loopback
test verifies a real redirect is not followed.

## Local verification

- `.venv/bin/python -m pytest -q tests/test_openai_adapter.py tests/test_openai_adapter_rust_compat.py`:
  68 passed.
- `cargo test -p agentrouter-cli --lib openai::tests --locked`: 3 passed.
- Strict Clippy for `agentrouter-cli`, Rust formatting, Ruff check/format, and
  `git diff --check`: passed.
- A live API call was not made.

## Review status

The Python and Rust response-status branches and their shared differential
fixtures were re-read after implementation. The code makes HTTP 200–299 the
only success range; invalid statuses fail before response parsing. No defect
was found in this local review. A separate reviewer has not yet reviewed this
small change; keep the task in `verify` until hosted CI and the required
independent review are complete.

## Release limits

No live provider call was made. The release gate remains unchanged and PR #16
remains held for its frozen context-band score and outstanding release checks.
