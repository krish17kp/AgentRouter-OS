# Independent audit — TASK-003

## verification-engineer — property tests PASS (genuine, non-vacuous)
- 6 property tests pass; `-m property` selects exactly those 6 (399 deselected).
- Hand-mutation of production logic: 7/8 injected bugs CAUGHT (auto-approve-everything,
  hardcoded needs_clarification, --risk precedence flip, confidence jitter, rate-limit
  off-by-one, idempotency body drop, task_preview leak). Properties are load-bearing.
- Found 1 WEAK SPOT: approval-mapping assertion read the classifier's own _APPROVAL
  table on both sides (tautological if the table itself is corrupted).
- importorskip verified in a fresh venv without hypothesis -> clean SKIP, not error.
- Full suite 405 passed.
- No production code changed; no security review needed (tests only).

## Repair applied
- Assert approval mapping against an INDEPENDENT literal (EXPECTED_APPROVAL), closing the
  tautology so a corrupted lookup table is now caught. Re-verified: 6 passed; full 405.
