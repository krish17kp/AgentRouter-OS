"""Two-annotator merge + disagreement adjudication (TASK-011).

Resolution rules for a candidate's collected labels:

* **Agreement** — all non-abstaining annotators chose the same band: accept it,
  no adjudicator needed, confidence is the mean of annotator confidences.
* **Unanimous abstention** — every annotator abstained: the item is recorded as
  abstained (context cannot be inferred honestly from the prompt alone).
* **Disagreement** — annotators chose different bands (or some abstained and some
  did not): the item is unresolved and requires an explicit adjudication.

Nothing here invents a label: a disagreement without an adjudication decision is
returned as unresolved so a human must decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from ..schema import ContextBand
from .schema import AdjudicatedItem, ItemLabels


@dataclass(frozen=True)
class Adjudication:
    """A human adjudicator's decision for a disagreed item."""

    adjudicator: str
    band: ContextBand | None  # None => the adjudicator confirms abstention
    abstain: bool
    rationale: str
    confidence: float = 0.6


def needs_adjudication(item: ItemLabels) -> bool:
    """True when annotators do not unanimously agree or unanimously abstain."""
    if len(item.labels) < 2:
        return True
    abstains = [label.abstain for label in item.labels]
    if all(abstains):
        return False
    bands = {label.band for label in item.labels if not label.abstain}
    # any abstention mixed with a band, or more than one distinct band -> conflict
    return any(abstains) or len(bands) != 1


def resolve(
    item: ItemLabels,
    *,
    label_source: str = "generated_candidate",
    adjudication: Adjudication | None = None,
) -> AdjudicatedItem | None:
    """Fold collected labels (plus an optional adjudication) into a final item.

    Returns None when the item disagrees and no adjudication was supplied — the
    caller must route it to a human. Never fabricates a band.
    """
    annotators = item.annotators

    if not needs_adjudication(item):
        if all(label.abstain for label in item.labels):
            return AdjudicatedItem(
                id=item.candidate_id,
                prompt=item.prompt,
                category=item.category,
                abstained=True,
                label_source=label_source,
                annotators=annotators,
                rationale="; ".join(label.rationale for label in item.labels),
                confidence=round(mean(label.confidence for label in item.labels), 4),
            )
        band = next(label.band for label in item.labels if not label.abstain)
        return AdjudicatedItem(
            id=item.candidate_id,
            prompt=item.prompt,
            category=item.category,
            band=band,
            label_source=label_source,
            annotators=annotators,
            rationale="; ".join(label.rationale for label in item.labels if not label.abstain),
            confidence=round(
                mean(label.confidence for label in item.labels if not label.abstain), 4
            ),
        )

    if adjudication is None:
        return None  # unresolved: a human must decide

    return AdjudicatedItem(
        id=item.candidate_id,
        prompt=item.prompt,
        category=item.category,
        band=None if adjudication.abstain else adjudication.band,
        abstained=adjudication.abstain,
        label_source=label_source,
        annotators=annotators,
        adjudicated_by=adjudication.adjudicator,
        rationale=adjudication.rationale,
        confidence=round(adjudication.confidence, 4),
    )
