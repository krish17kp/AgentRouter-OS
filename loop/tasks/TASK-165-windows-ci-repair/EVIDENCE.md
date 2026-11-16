# TASK-165 evidence

Hosted Windows CI at `79c70b0` reproduced two platform-specific failures:

- `Command::new("agentrouter")` found the real executable beside the grading
  probe before consulting the fixture-only PATH.
- Python `Path.open("xb")` followed a dangling Windows reparse point introduced
  immediately before open.

Runtime CLI discovery now accepts an explicit executable path through
`AGENTROUTER_EVALUATION_CLI`; production remains PATH-based. Diagnostic bundle
creation uses POSIX `O_EXCL|O_NOFOLLOW` and Windows
`CreateFileW(CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT)`. Windows handle transfer
and every error path close the correct owner.

Independent review found one post-transfer descriptor leak; it was repaired and
re-review is clear. Focused bundle/evaluation checks pass 46/46, Ruff and format
pass, and strict evaluation Clippy passes. Hosted Windows confirmation is
pending the RC push.
