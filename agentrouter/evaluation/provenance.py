"""Provenance + leakage controls (program §8, §14).

Captures the environment snapshot for a run and computes dataset-quality /
leakage reports. Honest labelling: distinguishes model_assisted from human.
"""

from __future__ import annotations

import hashlib
import platform
import sys
from collections import Counter
from pathlib import Path

from .schema import AnnotationMethod, EvaluationCase


def file_checksum(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def environment_snapshot(git_sha: str | None = None) -> dict:
    """Reproducibility metadata for a run. git_sha passed in (no Date.now/random)."""
    try:
        from importlib.metadata import version

        ar_version = version("agentrouter-os")
    except Exception:  # noqa: BLE001 - version lookup is best-effort
        ar_version = "unknown"
    return {
        "agentrouter_version": ar_version,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_sha": git_sha,
    }


def dataset_quality(cases: list[EvaluationCase]) -> dict:
    """Distribution + leakage report over a case list (program §14)."""
    hashes = [c.task_hash for c in cases]
    exact_dupes = len(hashes) - len(set(hashes))

    # paraphrase-family split leakage: a family must not straddle splits
    fam_splits: dict[str, set[str]] = {}
    for c in cases:
        if c.paraphrase_group:
            fam_splits.setdefault(c.paraphrase_group, set()).add(c.source_split or "default")
    leaked_families = sorted(f for f, s in fam_splits.items() if len(s) > 1)

    def dist(values) -> dict[str, int]:
        return dict(Counter(v for v in values if v is not None))

    return {
        "n_cases": len(cases),
        "exact_duplicates": exact_dupes,
        "paraphrase_families": len(fam_splits),
        "leaked_paraphrase_families": leaked_families,
        "language_distribution": dist(c.language for c in cases),
        "domain_distribution": dist(c.domain for c in cases),
        "risk_distribution": dist(r.value for c in cases for r in (c.expected.risks[:1] or [])),
        "task_type_distribution": dist(
            t.value for c in cases for t in (c.expected.task_types[:1] or [])
        ),
        "provenance_distribution": dist(c.provenance.method.value for c in cases),
        "model_assisted_count": sum(
            1 for c in cases if c.provenance.method == AnnotationMethod.model_assisted
        ),
    }
