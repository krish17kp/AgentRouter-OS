"""Evaluation runner (program §7 profiles).

Loads the requested datasets, grades the classifier over the combined case set,
and attaches an environment + dataset-quality snapshot for reproducibility.
"""

from __future__ import annotations

import subprocess

from .grading import grade
from .provenance import dataset_quality, environment_snapshot
from .registry import get_adapter, profile_datasets
from .schema import EvaluationCase


def _git_sha() -> str | None:
    try:
        out = subprocess.run(  # nosec B603 B607 - fixed argv, dev-only git SHA capture
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:  # noqa: BLE001 - git is optional at runtime
        return None


def _collect(
    names: list[str], limit: int | None, seed: int, source: str
) -> tuple[list[EvaluationCase], dict]:
    from .base import SkippedExternal

    cases: list[EvaluationCase] = []
    per_dataset: dict[str, dict] = {}
    for name in names:
        adapter = get_adapter(name)
        try:
            sampled = adapter.sample(limit=limit, seed=seed, source=source)
        except SkippedExternal as e:
            # Real (or unavailable fixture) data is missing — never silently skip
            # silently: record the exact blocker so the report is honest.
            per_dataset[name] = {
                "status": "SKIPPED_EXTERNAL",
                "n": 0,
                "blocker": str(e),
                **adapter.describe(),
            }
            continue
        cases.extend(sampled)
        per_dataset[name] = {
            "status": f"real:{name}" if source == "real" else adapter.availability().value,
            "n": len(sampled),
            "checksum": adapter.checksum(source=source),
            **adapter.describe(),
        }
    return cases, per_dataset


def run(
    *,
    profile: str | None = None,
    dataset: str | None = None,
    limit: int | None = None,
    seed: int = 0,
    languages: list[str] | None = None,
    source: str = "fixture",
    measure_all: bool = False,
) -> dict:
    """Run an evaluation for a profile or a single dataset. Returns the result."""
    if dataset:
        names = [dataset]
    elif profile:
        names = profile_datasets(profile)
    else:
        names = profile_datasets("fast")

    # MASSIVE supports language filtering — thread it through when requested
    if dataset == "massive" and languages:
        from .adapters.massive import MassiveAdapter
        from .base import SkippedExternal

        adapter = MassiveAdapter(languages=languages)
        try:
            cases = adapter.sample(limit=limit, seed=seed, source=source)
            per_dataset = {"massive": {"status": adapter.availability().value, "n": len(cases)}}
        except SkippedExternal as e:
            cases, per_dataset = (
                [],
                {"massive": {"status": "SKIPPED_EXTERNAL", "n": 0, "blocker": str(e)}},
            )
    else:
        cases, per_dataset = _collect(names, limit, seed, source)

    result = grade(cases, measure_all=measure_all)
    result["environment"] = environment_snapshot(_git_sha())
    result["datasets"] = per_dataset
    result["profile"] = profile
    result["dataset_quality"] = dataset_quality(cases)
    result["seed"] = seed
    result["source"] = source
    return result
