"""Banking77 adapter (program §5.7) — financial language + risk calibration.

Fixture mode (offline, default) proves risk is calibrated to the *action*, not
the domain. Real mode loads the official `PolyAI/banking77` dataset via the
`datasets` lib. Every banking77 record is an end-user customer query (no
production-mutation actions), so real records map to informational task types
at low risk — which is exactly the point: a banking sentence is not high risk
by virtue of being about money. Mapping is provenance=heuristic, pending review.
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
)

_FIXTURE = (
    Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "banking77_sample.jsonl"
)


class Banking77Adapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="banking77",
        version="v1",
        license="MIT",
        source="https://huggingface.co/datasets/PolyAI/banking77",
        description="Fine-grained banking intent queries used to check financial "
        "language handling and action-based risk calibration.",
        requires_network=True,
    )
    fixture_path = _FIXTURE
    hf_repo = "PolyAI/banking77"

    def availability(self) -> Availability:
        if self.fixture_path and self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def _load_real(self) -> list[EvaluationCase]:
        ds = self._hf_load(split="test")
        label_names = ds.features["label"].names
        out: list[EvaluationCase] = []
        seen: set[str] = set()
        for i, row in enumerate(ds):
            text = row["text"].strip()
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            intent = label_names[row["label"]]
            out.append(
                EvaluationCase(
                    id=f"banking77-{i}",
                    dataset=self.meta.name,
                    dataset_version=self.meta.version,
                    source=self.meta.source,
                    source_split="test",
                    task=text,
                    domain="banking",
                    tags=[intent],
                    # customer queries: informational, low risk (calibrated to action)
                    expected=ExpectedClassification(
                        task_types=["general", "analysis"], risks=["low"]
                    ),
                    provenance=Provenance(
                        method=AnnotationMethod.heuristic,
                        source_license="MIT",
                        source_record_id=str(i),
                    ),
                    review_status=ReviewStatus.pending,
                    notes=f"banking77_intent={intent}",
                )
            )
        return out
