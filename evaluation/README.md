# AgentRouter OS — Evaluation

Graded evaluation of the classifier + router against a human gold benchmark and
seven public/external benchmarks. Everything here runs **offline with no API
keys**; heavy dependencies live in optional extras.

## Quick start
```bash
pip install -e ".[dev]"
python -m agentrouter eval list-datasets
python -m agentrouter eval run --profile fast          # gold only, offline
python -m agentrouter eval run --profile nightly        # + clinc/banking/massive fixtures
python -m agentrouter eval report artifacts/evaluation/current/result.json
```

## Layout
| Path | What |
|------|------|
| `agentrouter/evaluation/` | framework code (schema, adapters, metrics, grading, reports, CLI) |
| `evaluation/fixtures/` | small committed smoke fixtures (one `EvaluationCase` JSON per line) |
| `benchmarks/*.yaml` | human gold benchmarks (classifier + routing) |
| `artifacts/evaluation/` | run outputs (`current/` is git-ignored; baseline is kept) |

## Datasets
See `dataset_manifest.yaml` for source, version, license, and availability of each.
Full external runs are **SKIPPED_EXTERNAL** by default — call each adapter's
`full_run_status()` for the exact prerequisites and commands.

## Honesty rules (enforced)
- Unmeasured grade dimensions count as **0** in the headline `grade_over_100`; we never
  rescale to hide unbuilt evaluators. `grade_of_measured` reports the measured-only number.
- Fixtures are **model-assisted synthetic** data, marked as such in provenance — never
  presented as an independent human holdout.
- An adapter that cannot reach its real data reports `SKIPPED_EXTERNAL`, never a fake pass.

Status of the wider program: see `../EVALUATION_STATUS.md` and `../EVALUATION_HANDOFF.md`.
