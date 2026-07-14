"""SWE-bench adapter (program §5.4).

SWE-bench grades whether an agent can *solve* a real GitHub issue by producing
a patch that passes the repo's tests — that requires the Docker evaluation
harness and is out of scope for offline CI. What AgentRouter grades here is
different and cheap: given the issue text alone, does the classifier *infer*
the right task_type / complexity / tool needs / context / tier / safety and
route it to a sufficiently capable coding model? So the fixture carries
synthetic-but-realistic issue descriptions with routing expectations, and the
full issue-solving run is reported as SKIPPED_EXTERNAL.
"""

from __future__ import annotations

from pathlib import Path

from ..base import Availability, DatasetAdapter, DatasetMetadata
from ..schema import (
    AnnotationMethod,
    EvaluationCase,
    ExpectedClassification,
    Provenance,
    ReviewStatus,
    RoutingExpectation,
)

_FIXTURE = Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "swebench_sample.jsonl"


class SWEBenchAdapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="swebench",
        version="lite",
        license="SWE-bench (MIT code; per-repo licenses apply)",
        source="https://www.swebench.com",
        description=(
            "Real-world GitHub issue resolution. AgentRouter grades inferred "
            "classification/routing from issue text, not actual issue-solving "
            "(that is the Docker harness full run)."
        ),
        requires_network=True,
        requires_docker=True,
    )

    fixture_path = _FIXTURE
    hf_repo = "princeton-nlp/SWE-bench_Lite"

    def availability(self) -> Availability:
        if self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def _load_real(self) -> list[EvaluationCase]:
        """Metadata-only real load: issue text + repo/commit. NO Docker, NO solving.

        This prepares the classification/routing inputs from real issues; actual
        patch generation + test execution stays in `full_run_status()`.
        """
        ds = self._hf_load(split="test")
        out: list[EvaluationCase] = []
        seen: set[str] = set()
        for i, row in enumerate(ds):
            problem = (row.get("problem_statement") or "").strip()
            if not problem or problem.lower() in seen:
                continue
            seen.add(problem.lower())
            out.append(
                EvaluationCase(
                    id=f"swebench-{row.get('instance_id', i)}",
                    dataset=self.meta.name,
                    dataset_version=self.meta.version,
                    source=self.meta.source,
                    source_split="test",
                    task=problem,
                    domain="software-engineering",
                    tags=["swe-bench", "issue", str(row.get("repo", ""))],
                    expected=ExpectedClassification(task_types=["coding"]),
                    routing=RoutingExpectation(minimum_ability={"coding": 7}),
                    provenance=Provenance(
                        method=AnnotationMethod.dataset_native,
                        source_license=self.meta.license,
                        source_record_id=str(row.get("instance_id", i)),
                    ),
                    review_status=ReviewStatus.pending,
                    notes=f"repo={row.get('repo')} base_commit={row.get('base_commit')}",
                )
            )
        return out

    def full_run_status(self) -> dict:
        return {
            "status": "SKIPPED_EXTERNAL",
            "reason": (
                "The real SWE-bench run resolves issues by building each repo in "
                "Docker and running its test suite against a generated patch. This "
                "needs the SWE-bench harness, a running Docker daemon, and "
                "model-generated predictions — none available in offline CI."
            ),
            "commands": [
                "pip install swebench",
                "# install and start Docker (daemon must be running)",
                "docker info",
                ("# 1) produce predictions.jsonl (one patch per instance) with your agent/model"),
                (
                    "python -m swebench.harness.run_evaluation "
                    "--dataset_name princeton-nlp/SWE-bench_Lite "
                    "--predictions_path predictions.jsonl "
                    "--max_workers 4 "
                    "--run_id agentrouter-full"
                ),
            ],
        }
