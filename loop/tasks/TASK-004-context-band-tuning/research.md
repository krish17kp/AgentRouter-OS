# Discover — TASK-004

Baseline context_band_accuracy = 0.824 (136/165). Failure analysis (classify vs gold):
- OVER-prediction (11, gold=small->pred=medium): M_EXISTING_CODE words (api/system/
  project/service/files) fire on reasoning/writing/general tasks -> wrongly medium.
  e.g. rea-003/004/008/015, wri-001/012, gen-001/003/008/012, cod-009.
- UNDER-prediction (18, gold=medium->pred=small): no signal for "operate on existing
  artifacts" (review/audit/investigate: ana-010, mix-009/011/015, sec-011) or data
  pipelines (pipeline/etl/ingestion/retrieval/vector-db: rag-003/007/008/010/013/015).
- Residual (debatable, will NOT keyword-hack): cod-021 websocket, cod-025, sec-006
  billing, sec-012 oauth2, sec-014 encrypt PII, bld-008 chat, mix-007 RFC.

Principled fix: (1) gate M_EXISTING_CODE bump on task_type in {coding, analysis};
(2) add M_REVIEW_EXISTING (review/audit/investigate/...) and M_DATA_PIPELINE nouns ->
medium. Semantic categories, not fixture words. Measure for regression + overfitting.
