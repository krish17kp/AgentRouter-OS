"""Per-dimension evaluators for the 100-point grade (program §6, §7).

Each ``evaluate_*`` returns ``{"score": float 0..1, "detail": {...}}`` grounded
in real computation over the live code — never a hardcoded constant. Dimensions
that can only be measured as a proxy DECLARE that in their detail.

``load_seed_models`` loads the packaged seed registry so routing/provider/
performance evaluators have a deterministic, offline model catalog to run
against (the same seeds ``agentrouter init`` ships).
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from ...registry import load_models, load_providers
from ...schema import ModelEntry
from .feedback import evaluate_feedback
from .performance import evaluate_performance
from .platform import evaluate_platform
from .provider import evaluate_provider
from .routing import evaluate_routing
from .safety import evaluate_safety


@lru_cache(maxsize=1)
def load_seed_models() -> tuple[ModelEntry, ...]:
    """The packaged seed model catalog (deterministic, offline). Cached."""
    seeds = resources.files("agentrouter") / "seeds"
    with resources.as_file(seeds) as path:
        providers = load_providers(path / "providers.yaml")
        models, _warnings = load_models(path / "models.yaml", providers)
    return tuple(models)


__all__ = [
    "load_seed_models",
    "evaluate_routing",
    "evaluate_safety",
    "evaluate_platform",
    "evaluate_provider",
    "evaluate_feedback",
    "evaluate_performance",
]
