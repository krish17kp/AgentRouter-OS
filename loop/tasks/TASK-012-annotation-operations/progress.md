# TASK-012 progress

Branch: `task/TASK-012-annotation-operations` (from `release/agentrouter-v0.5-rc1`).
Status: **tooling + operator docs built**; the human labelling round itself is the
external step (two real annotators + adjudicator).

## Delivered

- `agentrouter/annotation/packs.py` — blinded pack operations:
  - `build_pack` (independent per-annotator randomised ordering over the same set),
  - `pending` / `progress` (resume + label-free counts),
  - `merge_by_candidate`, `disagreement_items`, `adjudication_candidates`
    (disagreements-only, blinded, no auto-adjudication; single-annotator items
    surfaced), `labels_to_csv`.
- CLI (`agentrouter dataset ...`): `pack`, resumable `annotate` (per-item save),
  `progress`, `export` (CSV), `adjudication-pack`.
- Operator docs: `ANNOTATOR_A_INSTRUCTIONS.md`, `ANNOTATOR_B_INSTRUCTIONS.md`,
  `ADJUDICATOR_INSTRUCTIONS.md`, `TASK_012_OWNER_ACTIONS.md` (exact commands;
  states plainly that two real people must label all 63 independently).
- Tests: `tests/test_annotation_packs.py` — ordering independence + same-set +
  determinism, blinding (no bands in packs), resume/progress label-free,
  disagreements-only adjudication, single-annotator surfacing, CSV export, and the
  CLI pack/annotate-resume/progress/export/adjudication-pack flow.

## Guardrails honoured

- Blinded: packs carry no bands/predictions; each annotator writes their own file;
  progress reveals counts only.
- No auto-adjudication; adjudication pack is disagreements-only; no fabricated or
  AI-as-human labels. Frozen holdout untouched; 0.90 gate unchanged.

## Note

Local pytest could not complete this session (environment killed every background
python run; 7/8 pack tests confirmed green before a kill, all module ops smoke-
tested, lint clean). GitHub CI is the authority for the full suite on this branch.

## Remaining (external)

- Two real annotators + adjudicator run the round per `TASK_012_OWNER_ACTIONS.md`
  to produce the human-labelled dev set + new private holdout.
