"""LongBench v2 adapter (program §5.5).

Long-context understanding. The full benchmark needs the HuggingFace dataset
and a model able to ingest very long inputs (up to and beyond 512k tokens),
so the full run is SKIPPED_EXTERNAL. The fixture exercises the classifier's
context-band inference across the length spectrum.

`CONTEXT_BUCKETS` are the five reporting buckets used to spread fixture cases
along the length axis; they are coarser than the classifier's own
small/medium/large bands and exist only to guarantee spectrum coverage.
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
    Path(__file__).resolve().parents[3] / "evaluation" / "fixtures" / "longbench_v2_sample.jsonl"
)

# (label, low_inclusive, high_exclusive) token buckets spanning the spectrum.
CONTEXT_BUCKETS: list[tuple[str, int, int]] = [
    ("under-8k", 0, 8_000),
    ("8k-32k", 8_000, 32_000),
    ("32k-128k", 32_000, 128_000),
    ("128k-512k", 128_000, 512_000),
    ("over-512k", 512_000, 1_000_000_000),
]


def bucket_for(tokens: int) -> str:
    """Return the CONTEXT_BUCKETS label a token count falls into."""
    for label, low, high in CONTEXT_BUCKETS:
        if low <= tokens < high:
            return label
    # tokens below 0 is nonsensical; clamp to the first bucket.
    return CONTEXT_BUCKETS[0][0]


class LongBenchV2Adapter(DatasetAdapter):
    meta = DatasetMetadata(
        name="longbench-v2",
        version="v2",
        license="LongBench v2 (see dataset card)",
        source="https://huggingface.co/datasets/THUDM/LongBench-v2",
        description=(
            "Long-context understanding across realistic length buckets. "
            "AgentRouter grades inferred context-band and routing."
        ),
        requires_network=True,
    )

    fixture_path = _FIXTURE
    hf_repo = "THUDM/LongBench-v2"

    def availability(self) -> Availability:
        if self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def _load_raw(self) -> list[EvaluationCase]:
        return self._load_fixture()

    def _load_real(self) -> list[EvaluationCase]:
        """Real static loader: reads questions + preserves context length/category.

        Token count is estimated from the context word count (~1.3 tokens/word);
        the actual long-context *model* run remains SKIPPED_EXTERNAL.
        """
        ds = self._hf_load(split="train")
        out: list[EvaluationCase] = []
        seen: set[str] = set()
        for i, row in enumerate(ds):
            question = (row.get("question") or "").strip()
            if not question or question.lower() in seen:
                continue
            seen.add(question.lower())
            context = row.get("context") or ""
            tokens = int(len(context.split()) * 1.3)
            band = "small" if tokens < 8_000 else "medium" if tokens < 32_000 else "large"
            out.append(
                EvaluationCase(
                    id=f"longbench-{row.get('_id', i)}",
                    dataset=self.meta.name,
                    dataset_version=self.meta.version,
                    source=self.meta.source,
                    source_split="train",
                    task=question,
                    domain=str(row.get("domain", "")),
                    tags=["long-context", bucket_for(tokens), str(row.get("difficulty", ""))],
                    context_tokens=tokens,
                    expected=ExpectedClassification(context_bands=[band]),
                    provenance=Provenance(
                        method=AnnotationMethod.dataset_native,
                        source_license=self.meta.license,
                        source_record_id=str(row.get("_id", i)),
                    ),
                    review_status=ReviewStatus.pending,
                    notes=f"longbench_domain={row.get('domain')} words={len(context.split())}",
                )
            )
        return out

    def full_run_status(self) -> dict:
        return {
            "status": "SKIPPED_EXTERNAL",
            "reason": (
                "The full LongBench v2 run downloads the HuggingFace dataset and "
                "evaluates a model on inputs up to and beyond 512k tokens. It needs "
                "network access to the Hub and a long-context-capable model, neither "
                "available in offline CI."
            ),
            "commands": [
                "pip install datasets",
                (
                    'python -c "from datasets import load_dataset; '
                    "load_dataset('THUDM/LongBench-v2', split='train')\""
                ),
                (
                    "# provide a long-context model (>=512k for the largest bucket) "
                    "and run the official LongBench v2 prediction + scoring scripts"
                ),
            ],
        }
