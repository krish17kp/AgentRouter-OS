"""Typed schema for the context-band annotation program (TASK-011).

Every artifact — candidates, per-annotator labels, adjudicated items, and the
versioned dataset manifest — is a pydantic model with ``extra='forbid'`` so
malformed data fails loudly at the boundary. A final label is either a
``ContextBand`` or an explicit abstention; confidence and rationale are recorded
with every label, and provenance records where each item and label came from.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schema import ContextBand
from . import CATEGORIES, SCHEMA_VERSION, SPLITS

# How a candidate prompt entered the pool. Generated candidates are UNLABELLED
# input to human review — never an automatic final label.
LABEL_SOURCES = ("generated_candidate", "curated", "real_prompt")


class Candidate(BaseModel):
    """An unlabelled prompt proposed for human annotation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str = Field(min_length=1)
    category: str
    source: str = "generated_candidate"
    template: str | None = None  # generation template id, when synthetic
    notes: str | None = None

    @model_validator(mode="after")
    def _check_enums(self) -> Candidate:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if self.source not in LABEL_SOURCES:
            raise ValueError(f"unknown source {self.source!r}")
        return self


class AnnotatorLabel(BaseModel):
    """One annotator's judgement for one candidate.

    ``abstain=True`` means the annotator could not honestly infer a band from the
    prompt alone; ``band`` is then None. Otherwise ``band`` is required.
    """

    model_config = ConfigDict(extra="forbid")

    annotator: str = Field(min_length=1)
    band: ContextBand | None = None
    abstain: bool = False
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    at: datetime | None = None

    @model_validator(mode="after")
    def _band_xor_abstain(self) -> AnnotatorLabel:
        if self.abstain and self.band is not None:
            raise ValueError("an abstained label must not carry a band")
        if not self.abstain and self.band is None:
            raise ValueError("a non-abstained label must carry a band")
        return self


class ItemLabels(BaseModel):
    """All annotator labels collected for a single candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    prompt: str
    category: str
    labels: list[AnnotatorLabel] = Field(default_factory=list)

    @property
    def annotators(self) -> list[str]:
        return [label.annotator for label in self.labels]

    @property
    def agrees(self) -> bool:
        """True when >=2 non-abstaining annotators exist and all bands match."""
        bands = [label.band for label in self.labels if not label.abstain]
        return len(bands) >= 2 and len(set(bands)) == 1


class AdjudicatedItem(BaseModel):
    """A finalised, human-reviewed dataset item with full provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str = Field(min_length=1)
    category: str
    band: ContextBand | None = None
    abstained: bool = False
    label_source: str  # provenance of the CANDIDATE (not the label)
    annotators: list[str] = Field(default_factory=list)
    adjudicated_by: str | None = None  # set only when annotators disagreed
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    split: str | None = None
    review_status: str = "pending_human_review"

    @model_validator(mode="after")
    def _check(self) -> AdjudicatedItem:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if self.label_source not in LABEL_SOURCES:
            raise ValueError(f"unknown label_source {self.label_source!r}")
        if self.split is not None and self.split not in SPLITS:
            raise ValueError(f"unknown split {self.split!r}")
        if self.abstained and self.band is not None:
            raise ValueError("an abstained item must not carry a band")
        if not self.abstained and self.band is None:
            raise ValueError("a banded item must carry a band")
        return self


class DatasetManifest(BaseModel):
    """Versioned provenance for a built dataset (train/dev/holdout)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    dataset: str = "agentrouter-context-band-v2"
    version: str
    created: str
    split_counts: dict[str, int] = Field(default_factory=dict)
    split_sha256: dict[str, str] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    band_counts: dict[str, int] = Field(default_factory=dict)
    frozen_holdout_untouched: bool = True
    leakage_report: str | None = None
    provenance: str = ""
