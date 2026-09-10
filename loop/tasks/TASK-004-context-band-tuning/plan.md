# Plan — TASK-004 context-band tuning (L4)

## Anti-overfitting stance (explicit)
Prior iter-8 stopped at 0.82 warning that forcing 0.90 overfits. So: only add signals
that are GENERAL semantic categories a human would agree imply larger context; refuse to
add fixture-specific keywords for the residual debatable cases.

## Change (agentrouter/classifier.py, _context_tokens only)
1. Gate the existing M_EXISTING_CODE bump (api/system/project/...) on task_type in
   {coding, analysis} — a reasoning/writing/general prompt that merely mentions "API" is a
   short instruction, not a large-context job. (fixes ~10 over-predictions)
2. Add M_REVIEW_EXISTING (review/audit/investigate/refactor/migrate/documentation) -> medium
   — acting on an existing artifact implies loaded context.
3. Add M_DATA_PIPELINE (pipeline/etl/ingestion/warehouse/retrieval/vector db/data validation)
   -> medium — multi-stage data systems carry substantial context.

## Deliberately NOT fixed (would require fixture-specific keywords = overfitting)
cod-021 websocket, cod-025, sec-006 billing, sec-012 oauth2, sec-014 encrypt PII,
bld-008 chat, mix-007 RFC, cod-009 (files), gen-008 (book). Left as honest residuals.

## Verification
Full eval (all 7 gates), full pytest, per-case gold analysis, regression test locking
context_band_accuracy>=0.90. Compatibility: only context_band changes; task_type/risk/etc
untouched.
