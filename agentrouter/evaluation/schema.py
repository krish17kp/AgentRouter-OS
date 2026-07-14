"""Normalized evaluation-case schema (program §3).

One EvaluationCase is the common currency every adapter emits. Expected labels
are *sets* so genuinely ambiguous prompts are not force-fit to one answer: a
prediction is correct when it lands in the acceptable set.

Reuses the canonical enums from agentrouter.schema — no parallel label universe.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..schema import ApprovalLevel, ContextBand, Level, OutputType, PricingTier, TaskType


class AnnotationMethod(str, Enum):
    human = "human"
    model_assisted = "model_assisted"
    heuristic = "heuristic"
    dataset_native = "dataset_native"


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


def normalized_hash(text: str) -> str:
    """Deterministic hash of a task, insensitive to case/whitespace punctuation.

    Used for duplicate + leakage detection across splits.
    """
    norm = re.sub(r"\s+", " ", text.strip().lower())
    norm = re.sub(r"[^\w\s]", "", norm)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: AnnotationMethod = AnnotationMethod.model_assisted
    reviewer: str | None = None
    source_license: str | None = None
    source_record_id: str | None = None
    retrieved: str | None = None  # ISO date the data was fetched


class ExpectedClassification(BaseModel):
    """Acceptable label sets for the 7 classifier dimensions. Empty = don't grade."""

    model_config = ConfigDict(extra="forbid")
    task_types: list[TaskType] = Field(default_factory=list)
    complexities: list[Level] = Field(default_factory=list)
    risks: list[Level] = Field(default_factory=list)
    context_bands: list[ContextBand] = Field(default_factory=list)
    output_types: list[OutputType] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    approval_levels: list[ApprovalLevel] = Field(default_factory=list)


class RoutingExpectation(BaseModel):
    """Constraint-based routing truth — never a hardcoded commercial model name."""

    model_config = ConfigDict(extra="forbid")
    minimum_ability: dict[str, int] = Field(default_factory=dict)
    acceptable_pricing_tiers: list[PricingTier] = Field(default_factory=list)
    permitted_providers: list[str] = Field(default_factory=list)
    forbidden_models: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    min_context_tokens: int | None = None


class SafetyExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_execute_allowed: bool | None = None
    must_require_human_approval: bool = False


class EvaluationCase(BaseModel):
    """One normalized case. `task` is the only strictly required semantic field."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dataset: str
    task: str
    dataset_version: str | None = None
    source: str | None = None
    source_split: str | None = None
    language: str = "en"
    domain: str | None = None
    tags: list[str] = Field(default_factory=list)
    paraphrase_group: str | None = None

    expected: ExpectedClassification = Field(default_factory=ExpectedClassification)
    routing: RoutingExpectation | None = None
    safety: SafetyExpectation | None = None

    context_tokens: int | None = None
    cost_metadata: dict = Field(default_factory=dict)
    model_outcomes: dict = Field(default_factory=dict)

    provenance: Provenance = Field(default_factory=Provenance)
    review_status: ReviewStatus = ReviewStatus.pending
    checksum: str | None = None
    notes: str | None = None

    @field_validator("task")
    @classmethod
    def _task_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be non-empty")
        return v

    @property
    def task_hash(self) -> str:
        return normalized_hash(self.task)

    def with_checksum(self) -> EvaluationCase:
        """Return a copy with the deterministic task checksum filled in."""
        return self.model_copy(update={"checksum": self.task_hash})
