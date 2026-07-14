"""CLINC150 adapter (program §5.6) — intent robustness / out-of-scope.

Fixture mode (offline, default) loads the committed smoke sample. Real mode
loads the official `clinc_oos` dataset (config "plus") via the `datasets` lib.
CLINC intents are mapped to *acceptable sets* of AgentRouter task families; the
mapping is deliberately conservative and marked provenance=heuristic — unmapped
intents fall back to [general] tagged "needs-review", and mapping coverage is
reported so we never imply every intent has one obvious label.
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

_FIXTURE = Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "clinc150_sample.jsonl"

# Conservative curated intent-substring -> acceptable task families. Anything
# not matched defaults to [general] and is tagged needs-review.
_INTENT_HINTS: dict[str, list[str]] = {
    "translate": ["writing", "general"],
    "definition": ["general", "writing"],
    "spelling": ["writing"],
    "calculator": ["general"],
    "math": ["reasoning", "general"],
    "how_busy": ["general"],
    "meaning_of_life": ["general"],
    "text": ["writing"],
    "todo": ["general"],
    "reminder": ["general"],
    "calendar": ["general"],
}


def map_intent(intent: str) -> tuple[list[str], bool]:
    """Return (acceptable_task_types, is_curated). oos handled by caller."""
    for hint, families in _INTENT_HINTS.items():
        if hint in intent:
            return families, True
    return ["general"], False


class CLINC150Adapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="clinc150",
        version="plus",
        license="CC BY 3.0",
        source="https://huggingface.co/datasets/clinc_oos",
        description="Intent classification with an explicit out-of-scope class; "
        "intents mapped to acceptable AgentRouter task families.",
        requires_network=True,
    )
    fixture_path = _FIXTURE
    hf_repo = "clinc_oos"
    hf_config = "plus"

    def availability(self) -> Availability:
        if self.fixture_path and self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def _load_real(self) -> list[EvaluationCase]:
        ds = self._hf_load(split="test")
        names = ds.features["intent"].names
        out: list[EvaluationCase] = []
        seen: set[str] = set()
        for i, row in enumerate(ds):
            text = row["text"].strip()
            if text.lower() in seen:  # dataset has near-dupes; keep unique tasks
                continue
            seen.add(text.lower())
            intent = names[row["intent"]]
            is_oos = intent == "oos"
            families = ["general"] if is_oos else map_intent(intent)[0]
            curated = False if is_oos else map_intent(intent)[1]
            out.append(
                EvaluationCase(
                    id=f"clinc-{i}",
                    dataset=self.meta.name,
                    dataset_version=self.meta.version,
                    source=self.meta.source,
                    source_split="test",
                    task=text,
                    domain="oos" if is_oos else "intent",
                    tags=["out-of-scope"]
                    if is_oos
                    else ([intent] if curated else [intent, "needs-review"]),
                    expected=ExpectedClassification(task_types=families),
                    provenance=Provenance(
                        method=AnnotationMethod.heuristic,
                        source_license="CC BY 3.0",
                        source_record_id=str(i),
                    ),
                    review_status=ReviewStatus.pending,
                    notes=f"clinc_intent={intent}",
                )
            )
        return out
