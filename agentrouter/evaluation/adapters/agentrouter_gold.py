"""AgentRouter gold adapter (program §5.1).

Reuses the existing human-labelled benchmark at benchmarks/classifier_gold_v1.yaml
(165 cases) — no data duplication. approval is derived from risk exactly as the
classifier derives it, so its acceptable set tracks the risk set.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..base import AdapterError, Availability, DatasetAdapter, DatasetMetadata
from ..schema import (
    AnnotationMethod,
    EvaluationCase,
    ExpectedClassification,
    Provenance,
    ReviewStatus,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_GOLD = _PROJECT_ROOT / "benchmarks" / "classifier_gold_v1.yaml"

_RISK_TO_APPROVAL = {
    "low": "auto",
    "medium": "notify",
    "high": "human-approval-required",
}


class AgentRouterGoldAdapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="agentrouter-gold",
        version="v1",
        license="project-internal (MIT repo)",
        source="benchmarks/classifier_gold_v1.yaml",
        description="Human-expectation gold labels for the 7-dimension classifier.",
    )

    def __init__(self, path: Path = _GOLD):
        self._path = path

    def availability(self) -> Availability:
        return Availability.READY if self._path.exists() else Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        if not self._path.exists():
            raise AdapterError(f"gold benchmark not found: {self._path}")
        doc = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
            raise AdapterError(f"{self._path}: expected a mapping with a 'cases' list")
        version = f"v{doc.get('version', 1)}"
        out: list[EvaluationCase] = []
        for row in doc["cases"]:
            risks = row.get("risk", [])
            approvals = [_RISK_TO_APPROVAL[r] for r in risks if r in _RISK_TO_APPROVAL]
            out.append(
                EvaluationCase(
                    id=row["id"],
                    dataset=self.meta.name,
                    dataset_version=version,
                    source=self.meta.source,
                    task=row["prompt"],
                    expected=ExpectedClassification(
                        task_types=row.get("task_type", []),
                        complexities=row.get("complexity", []),
                        risks=risks,
                        output_types=row.get("output_type", []),
                        required_tools=row.get("tools", []),
                        context_bands=row.get("context_band", []),
                        approval_levels=approvals,
                    ),
                    provenance=Provenance(method=AnnotationMethod.human, source_license="MIT"),
                    review_status=ReviewStatus.approved,
                )
            )
        return out
