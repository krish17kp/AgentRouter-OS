"""Blinded annotation-pack operations (TASK-012).

Turns the shared candidate pool into independent, blinded packs — one per
annotator, each in its own randomised order — and supports resume, label-free
progress, CSV export, and a disagreements-only adjudication pack. Blinding is
structural: a pack contains only ``id``/``prompt``/``category`` (never a band, a
prediction, or another annotator's answer), and each annotator writes to their
own labels file.

Nothing here assigns or infers a label, and the adjudication pack is built purely
from where two humans disagree — it never auto-resolves.
"""

from __future__ import annotations

import csv
import io
import random

from .adjudicate import needs_adjudication
from .schema import Candidate, ItemLabels


def build_pack(candidates: list[Candidate], *, seed: int) -> list[Candidate]:
    """Return the candidates in a deterministic, per-seed randomised order.

    Different annotators pass different seeds, so their orderings are independent.
    Candidate content is unchanged (still unlabelled); only order differs.
    """
    order = list(candidates)
    random.Random(seed).shuffle(order)  # nosec B311 - ordering only, not security
    return order


def labelled_ids(labels: list[ItemLabels]) -> set[str]:
    return {item.candidate_id for item in labels}


def pending(candidates: list[Candidate], done: list[ItemLabels]) -> list[Candidate]:
    """Candidates not yet labelled — the resume queue for an interrupted session."""
    seen = labelled_ids(done)
    return [c for c in candidates if c.id not in seen]


def progress(candidates: list[Candidate], done: list[ItemLabels]) -> dict[str, int]:
    """Label-free progress: counts only, never the bands themselves."""
    total = len(candidates)
    complete = len(labelled_ids(done) & {c.id for c in candidates})
    return {"total": total, "done": complete, "remaining": total - complete}


def merge_by_candidate(*label_sets: list[ItemLabels]) -> dict[str, ItemLabels]:
    """Merge several annotators' label files, keyed by candidate id."""
    merged: dict[str, ItemLabels] = {}
    for labels in label_sets:
        for item in labels:
            if item.candidate_id in merged:
                merged[item.candidate_id].labels.extend(item.labels)
            else:
                merged[item.candidate_id] = item.model_copy(deep=True)
    return merged


def disagreement_items(*label_sets: list[ItemLabels]) -> list[ItemLabels]:
    """Only the merged items where annotators disagree (need adjudication).

    Requires every returned item to carry >= 2 annotator labels, so a candidate
    labelled by just one annotator is surfaced (as needing the second) rather than
    silently accepted.
    """
    merged = merge_by_candidate(*label_sets)
    return [item for item in merged.values() if needs_adjudication(item)]


def adjudication_candidates(*label_sets: list[ItemLabels]) -> list[Candidate]:
    """Blinded candidate pack for the adjudicator: disagreements only, no bands."""
    return [
        Candidate(
            id=item.candidate_id, prompt=item.prompt, category=item.category, source="curated"
        )
        for item in disagreement_items(*label_sets)
    ]


def labels_to_csv(labels: list[ItemLabels]) -> str:
    """Flatten labels to CSV rows (one per annotator label)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "candidate_id",
            "prompt",
            "category",
            "annotator",
            "band",
            "abstain",
            "rationale",
            "confidence",
        ]
    )
    for item in labels:
        for label in item.labels:
            writer.writerow(
                [
                    item.candidate_id,
                    item.prompt,
                    item.category,
                    label.annotator,
                    label.band.value if label.band else "",
                    label.abstain,
                    label.rationale,
                    label.confidence,
                ]
            )
    return buf.getvalue()
