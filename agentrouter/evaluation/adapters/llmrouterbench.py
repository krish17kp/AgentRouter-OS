"""LLMRouterBench adapter (program §5.2).

Routing quality under a cost/quality tradeoff: each case ships per-model
outcomes (quality in [0,1], cost) so a router is graded on picking a model that
meets the quality bar at acceptable cost. The full run needs the benchmark's
model outputs, which reference commercial models by name — AgentRouter never
hardcodes commercial names in routing logic, so a caller-supplied model-mapping
file is required to translate benchmark model keys onto registry entries.
"""

from __future__ import annotations

from pathlib import Path

from ..base import Availability, DatasetAdapter, DatasetMetadata
from ..schema import EvaluationCase

_FIXTURE = (
    Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "llmrouterbench_sample.jsonl"
)


class LLMRouterBenchAdapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="llmrouterbench",
        version="v1",
        license="see benchmark repo",
        source="LLMRouterBench",
        description=(
            "Routing quality with cost/quality tradeoffs. Each case carries "
            "per-model quality/cost outcomes; grading needs a caller-supplied "
            "model-mapping file (no commercial names in routing logic)."
        ),
        requires_network=True,
    )

    fixture_path = _FIXTURE

    def availability(self) -> Availability:
        if self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def model_mapping_required(self) -> bool:
        """True: benchmark model keys must be mapped onto registry entries."""
        return True

    def describe(self) -> dict:
        d = super().describe()
        d["model_mapping_required"] = self.model_mapping_required()
        d["model_mapping_note"] = (
            "Provide a model-mapping file translating LLMRouterBench model keys "
            "to registry entries; commercial names never appear in routing logic."
        )
        return d

    def full_run_status(self) -> dict:
        return {
            "status": "SKIPPED_EXTERNAL",
            "reason": (
                "The full LLMRouterBench run consumes the benchmark's per-model "
                "outputs (keyed by commercial model names) and a model-mapping file "
                "onto registry entries, then scores router cost/quality. Cloning the "
                "repo and supplying the mapping are out of scope for offline CI."
            ),
            "commands": [
                "git clone <LLMRouterBench repo> llmrouterbench && cd llmrouterbench",
                "pip install -r requirements.txt",
                (
                    "# create model_mapping.yaml mapping benchmark model keys -> "
                    "registry model keys (provider/model_id)"
                ),
                (
                    "python -m agentrouter.evaluation.cli run --dataset llmrouterbench "
                    "--model-mapping model_mapping.yaml"
                ),
            ],
        }
