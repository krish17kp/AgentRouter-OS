# TASK-010 evidence

Status: awaiting the first real GitHub-hosted Linux campaign.

Local deterministic evidence:

- `python -m pytest tests/test_mutation_ci.py -q` -> 8 passed.
- `ruff check scripts/run_mutation_ci.py tests/test_mutation_ci.py` -> clean.
- `pyproject.toml` parses with `tomllib`.
- all workflow YAML files parse with PyYAML.

No mutation score is recorded here until the Linux workflow completes.
