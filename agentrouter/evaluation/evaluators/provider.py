"""Provider registry evaluator (§7 provider_registry, weight 8).

Loads the seed registry and checks metadata completeness per model: vendor,
model_id, release_channel, context_window, and provenance (a real ``source``
plus a ``last_updated`` date) must be populated with non-placeholder values.
Score = fraction of models passing the check.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...schema import ModelEntry

_PLACEHOLDERS = {"", "unknown", "tbd", "todo", "placeholder", "n/a", "none"}


def _clean(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in _PLACEHOLDERS


def _check(m: ModelEntry) -> list[str]:
    """Return the list of missing/placeholder metadata fields for one model."""
    missing: list[str] = []
    if not _clean(m.vendor):
        missing.append("vendor")
    if not _clean(m.model_id):
        missing.append("model_id")
    if not (m.release_channel and _clean(m.release_channel.value)):
        missing.append("release_channel")
    if not (isinstance(m.context_window, int) and m.context_window > 0):
        missing.append("context_window")
    # provenance = a real source AND a last_updated date
    if not _clean(m.source):
        missing.append("provenance.source")
    if m.last_updated is None:
        missing.append("provenance.last_updated")
    return missing


def evaluate_provider(models: Sequence[ModelEntry] | None = None) -> dict:
    """Fraction of registry models with complete, non-placeholder metadata."""
    if models is None:
        from . import load_seed_models

        models = load_seed_models()
    models = list(models)
    failures: list[dict] = []
    for m in models:
        missing = _check(m)
        if missing:
            failures.append({"model": m.key, "missing": missing})
    n = len(models)
    passed = n - len(failures)
    return {
        "score": round(passed / n, 4) if n else 0.0,
        "detail": {
            "n_models": n,
            "passed": passed,
            "fields_checked": [
                "vendor",
                "model_id",
                "release_channel",
                "context_window",
                "provenance.source",
                "provenance.last_updated",
            ],
            "failures": failures,
        },
    }
