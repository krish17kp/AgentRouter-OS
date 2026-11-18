# TASK-146 — OpenAI status mutation coverage

## Objective

Ensure the critical mutation suite directly exercises the OpenAI response
status branch introduced by TASK-144.

## Scope

- Add direct adapter tests to `tests/test_openai_adapter.py`, which is part of
  the critical mutation workflow's selected suite.
- Exercise the valid status boundaries 200 and 299 and representative invalid
  statuses below, within, and above the non-2xx ranges.
- Reject absent and malformed response status metadata instead of accepting a
  body when the transport has not supplied a valid HTTP status.
- Preserve the existing numeric mutation thresholds and the no-unreviewed-
  survivor gate.

## Acceptance

- The focused adapter tests pass without live API calls, and the missing-status
  mutation is killed by the selected suite.
- Hosted critical mutation reports zero unreviewed survivors and passes every
  existing numeric and completeness threshold.
- No mutation threshold or allowlist is weakened to obtain a pass.
