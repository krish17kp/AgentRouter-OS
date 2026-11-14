# Test-first contract — TASK-004

New tests/test_context_band.py:
- gate: reasoning/writing/general prompts mentioning api/system/project stay SMALL (5 cases).
- existing-artifact + pipeline tasks are MEDIUM (7 cases).
- gold-accuracy guard: context_band_accuracy >= 0.90 over benchmarks/classifier_gold_v1.yaml.

Regression: full eval all-gates PASS; full `pytest -q` green (418).
