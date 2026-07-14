"""MASSIVE adapter (program §5.8) — multilingual intent classification.

Fixture mode (offline, default) covers en/hi/fr. Real mode loads the official
`AmazonScience/massive` dataset via the `datasets` lib, one HF config per
locale (e.g. en-US, hi-IN, fr-FR). `language` is preserved on every case so the
report can slice per-language, and intent/scenario/split/source id are kept.

Construct with `MassiveAdapter(languages=["en", "hi"])` to restrict languages.
"""

from __future__ import annotations

from pathlib import Path

from ..base import FIXTURE, REAL, Availability, DatasetAdapter, DatasetMetadata, SkippedExternal
from ..schema import (
    AnnotationMethod,
    EvaluationCase,
    ExpectedClassification,
    Provenance,
    ReviewStatus,
)

_FIXTURE = Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "massive_sample.jsonl"

# short language code -> MASSIVE HF locale config
_LOCALE = {"en": "en-US", "hi": "hi-IN", "fr": "fr-FR"}


class MassiveAdapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="massive",
        version="1.1",
        license="CC BY 4.0",
        source="https://huggingface.co/datasets/AmazonScience/massive",
        description="Multilingual (51-language) intent classification; the smoke "
        "fixture covers en/hi/fr for per-language reporting.",
        requires_network=True,
        languages=("en", "hi", "fr"),
    )
    fixture_path = _FIXTURE
    hf_repo = "AmazonScience/massive"

    def __init__(self, languages: list[str] | None = None):
        self._languages = languages

    def availability(self) -> Availability:
        if self.fixture_path and self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def _load_real(self) -> list[EvaluationCase]:
        langs = self._languages or list(_LOCALE)
        out: list[EvaluationCase] = []
        seen: set[str] = set()
        for lang in langs:
            locale = _LOCALE.get(lang)
            if not locale:
                raise SkippedExternal(f"massive: no HF locale mapping for '{lang}'")
            self.hf_config = locale
            ds = self._hf_load(split="test")
            for i, row in enumerate(ds):
                text = row["utt"].strip()
                key = f"{lang}:{text.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    EvaluationCase(
                        id=f"massive-{lang}-{i}",
                        dataset=self.meta.name,
                        dataset_version=self.meta.version,
                        source=self.meta.source,
                        source_split="test",
                        task=text,
                        language=lang,
                        domain=str(row.get("scenario", "")),
                        tags=[f"intent:{row.get('intent', '')}"],
                        expected=ExpectedClassification(task_types=["general"]),
                        provenance=Provenance(
                            method=AnnotationMethod.heuristic,
                            source_license="CC BY 4.0",
                            source_record_id=f"{locale}:{i}",
                        ),
                        review_status=ReviewStatus.pending,
                        notes=f"massive_locale={locale}",
                    )
                )
        return out

    def load(self, source: str = FIXTURE) -> list[EvaluationCase]:
        # Real mode already restricts by language; fixture mode filters after load.
        if source == REAL:
            return super().load(source=REAL)
        cases = super().load(source=source)
        if self._languages is None:
            return cases
        wanted = set(self._languages)
        return [c for c in cases if c.language in wanted]
