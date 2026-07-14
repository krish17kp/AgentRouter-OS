"""TwinRouterBench adapter (program §5.3).

Multi-agent workflow routing. Two tracks:
  - static  : each case is one agent step with a target tier; graded straight
              from the committed fixture (this adapter).
  - dynamic : replays whole workflows through a containerized agent runtime to
              measure live routing decisions — needs Docker, so the full run is
              reported SKIPPED_EXTERNAL.
"""

from __future__ import annotations

from pathlib import Path

from ..base import Availability, DatasetAdapter, DatasetMetadata
from ..schema import EvaluationCase

_FIXTURE = (
    Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "twinrouterbench_sample.jsonl"
)


class TwinRouterBenchAdapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="twinrouterbench",
        version="v1",
        license="see benchmark repo",
        source="TwinRouterBench",
        description=(
            "Multi-agent workflow routing. Static track graded from fixture; "
            "dynamic track replays workflows in Docker (full run only)."
        ),
        requires_network=True,
        requires_docker=True,
    )

    fixture_path = _FIXTURE

    def availability(self) -> Availability:
        if self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        # static track only — one case per agent step from the fixture
        return self._load_fixture()

    def full_run_status(self) -> dict:
        return {
            "status": "SKIPPED_EXTERNAL",
            "reason": (
                "The dynamic track replays full multi-agent workflows through a "
                "containerized agent runtime to measure live per-step routing. It "
                "requires a running Docker daemon and the benchmark's workflow "
                "images, neither available in offline CI. The static track is "
                "covered here from the committed fixture."
            ),
            "commands": [
                "git clone <TwinRouterBench repo> twinrouterbench && cd twinrouterbench",
                "# install and start Docker (daemon must be running)",
                "docker info",
                "docker compose up -d  # bring up the workflow runtime",
                "python -m twinrouterbench.run --track dynamic --router agentrouter",
            ],
        }
