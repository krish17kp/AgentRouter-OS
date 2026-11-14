"""Deterministic, leakage-safe train/dev/private-holdout partitioning (TASK-011).

Guarantees:
  * near-duplicate prompts never straddle a split boundary (whole clusters move
    together), so a train item cannot leak its answer into dev/holdout;
  * the new dev and holdout splits are checked against the frozen TASK-009 holdout
    and refuse to include any exact/near duplicate of it;
  * assignment is deterministic (hash of the cluster's canonical prompt), so the
    same input always yields the same splits.

Checking against the frozen holdout is a *leakage guard*, not tuning: no frozen
label is read and no model is fit or selected on it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from .dedup import cluster, find_leakage, normalize
from .schema import AdjudicatedItem

# fractional targets; holdout stays a genuine minority private set
DEFAULT_RATIOS = {"train": 0.6, "dev": 0.25, "holdout": 0.15}


class LeakageError(RuntimeError):
    """Raised when a proposed dev/holdout split overlaps the frozen holdout."""


@dataclass(frozen=True)
class SplitResult:
    train: list[AdjudicatedItem]
    dev: list[AdjudicatedItem]
    holdout: list[AdjudicatedItem]

    def as_dict(self) -> dict[str, list[AdjudicatedItem]]:
        return {"train": self.train, "dev": self.dev, "holdout": self.holdout}


def _bucket(cluster_key: str, ratios: dict[str, float]) -> str:
    """Deterministically map a cluster to a split by hashing its key."""
    h = int(hashlib.sha256(cluster_key.encode("utf-8")).hexdigest(), 16)
    point = (h % 10_000) / 10_000
    cumulative = 0.0
    for name in ("train", "dev", "holdout"):
        cumulative += ratios[name]
        if point < cumulative:
            return name
    return "holdout"


def partition(
    items: list[AdjudicatedItem],
    *,
    frozen_holdout_prompts: Iterable[str] = (),
    ratios: dict[str, float] | None = None,
) -> SplitResult:
    """Split items into train/dev/holdout, cluster-aware and leakage-checked."""
    ratios = ratios or DEFAULT_RATIOS
    prompts = [i.prompt for i in items]
    clusters = cluster(prompts)

    assigned: dict[str, list[AdjudicatedItem]] = {"train": [], "dev": [], "holdout": []}
    for group in clusters:
        # canonical key = smallest normalised prompt in the cluster (stable)
        key = min(normalize(prompts[idx]) for idx in group)
        split = _bucket(key, ratios)
        for idx in group:
            assigned[split].append(items[idx].model_copy(update={"split": split}))

    frozen = list(frozen_holdout_prompts)
    if frozen:
        for split in ("dev", "holdout"):
            leaks = find_leakage([i.prompt for i in assigned[split]], frozen)
            if leaks:
                sample = leaks[0]
                raise LeakageError(
                    f"{split} split leaks against the frozen holdout: "
                    f"{sample.kind} match {sample.left!r} ~ {sample.right!r} "
                    f"(score {sample.score})"
                )

    return SplitResult(
        train=sorted(assigned["train"], key=lambda i: i.id),
        dev=sorted(assigned["dev"], key=lambda i: i.id),
        holdout=sorted(assigned["holdout"], key=lambda i: i.id),
    )
