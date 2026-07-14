"""RoutingEngine — eligibility filters, scoring, fallback (ROUTING_RULES.md §2-5)."""

from __future__ import annotations

from . import taxonomy
from .controls import PREFERENCE_WEIGHTS
from .schema import (
    Classification,
    ContextBand,
    DeprecationStatus,
    LatencyTier,
    Level,
    ModelEntry,
    PricingTier,
    TaskType,
)

# capability blend per task_type (ROUTING_RULES.md §3)
_CAP_BLEND: dict[TaskType, dict[str, float]] = {
    TaskType.coding: {"coding": 1.0},
    TaskType.reasoning: {"reasoning": 1.0},
    TaskType.writing: {"writing": 1.0},
    TaskType.analysis: {"reasoning": 0.7, "writing": 0.3},
    TaskType.summarization: {"writing": 0.7, "reasoning": 0.3},
    TaskType.general: {"coding": 1 / 3, "reasoning": 1 / 3, "writing": 1 / 3},
}

# cost_fit: pricing tier suitability per complexity
_COST_FIT: dict[Level, dict[PricingTier, float]] = {
    Level.low: {
        PricingTier.free: 1.0,
        PricingTier.low: 0.9,
        PricingTier.medium: 0.6,
        PricingTier.high: 0.3,
        PricingTier.frontier: 0.1,
    },
    Level.medium: {
        PricingTier.free: 0.7,
        PricingTier.low: 0.8,
        PricingTier.medium: 1.0,
        PricingTier.high: 0.8,
        PricingTier.frontier: 0.6,
    },
    Level.high: {
        PricingTier.free: 0.4,
        PricingTier.low: 0.5,
        PricingTier.medium: 0.7,
        PricingTier.high: 0.9,
        PricingTier.frontier: 1.0,
    },
}

_LAT_FIT: dict[Level, dict[LatencyTier, float]] = {
    Level.low: {LatencyTier.fast: 1.0, LatencyTier.medium: 0.7, LatencyTier.slow: 0.3},
    Level.medium: {LatencyTier.fast: 0.9, LatencyTier.medium: 0.8, LatencyTier.slow: 0.5},
    Level.high: {LatencyTier.fast: 0.8, LatencyTier.medium: 0.8, LatencyTier.slow: 0.6},
}

BASE_WEIGHTS = {"w_cap": 0.45, "w_cost": 0.25, "w_lat": 0.15, "w_ctx": 0.15}
_DEPRECATION_PENALTY = 0.2
_IDEAL_BOOST = 0.05
_AVOID_PENALTY = 0.10


def weights_for(
    cls: Classification, base: dict[str, float] | None = None, prefer: str | None = None
) -> tuple[dict, list[str]]:
    # An explicit user preference is a fixed weight vector that wins over the
    # complexity/context shifts below (they are skipped).
    if prefer is not None:
        return dict(PREFERENCE_WEIGHTS[prefer]), [f"preference={prefer} -> fixed weights"]
    w = dict(base or BASE_WEIGHTS)
    shifts: list[str] = []
    if cls.complexity is Level.high or cls.risk is Level.high:
        w["w_cap"], w["w_cost"] = 0.55, 0.15
        shifts.append("complexity/risk=high -> w_cap 0.55, w_cost 0.15")
    elif cls.complexity is Level.low:
        w["w_cap"], w["w_cost"] = 0.35, 0.35
        shifts.append("complexity=low -> w_cap 0.35, w_cost 0.35")
    if cls.context_band is ContextBand.large:
        w["w_ctx"], w["w_lat"] = 0.25, 0.05
        shifts.append("context=large -> w_ctx 0.25, w_lat 0.05")
    return w, shifts


def eligibility(
    models: list[ModelEntry], cls: Classification
) -> tuple[list[ModelEntry], list[dict]]:
    """Hard filters (ROUTING_RULES.md §2). Returns (eligible, excluded-with-reasons)."""
    eligible, excluded = [], []
    for m in models:
        if m.deprecation_status is DeprecationStatus.retired:
            excluded.append({"model": m.key, "reason": "retired"})
            continue
        if m.context_window < cls.context_tokens:
            excluded.append(
                {"model": m.key, "reason": f"context {m.context_window} < {cls.context_tokens}"}
            )
            continue
        needed = [t for t in cls.tool_needs if t != "vision"]
        support = set(m.tool_support)
        missing = [t for t in needed if not taxonomy.satisfied_by(t, support)]
        if missing:
            excluded.append({"model": m.key, "reason": f"missing tools: {','.join(missing)}"})
            continue
        if "vision" in cls.tool_needs and not m.vision_support:
            excluded.append({"model": m.key, "reason": "no vision support"})
            continue
        eligible.append(m)
    return eligible, excluded


def _capability_match(m: ModelEntry, cls: Classification) -> float:
    blend = _CAP_BLEND[cls.task_type]
    return sum(getattr(m.ability, dim) / 10 * w for dim, w in blend.items())


def _context_fit(m: ModelEntry, cls: Classification) -> float:
    # fits comfortably > barely fits > vastly oversized
    ratio = m.context_window / max(cls.context_tokens, 1)
    if ratio < 2:
        return 0.7  # barely fits
    if ratio < 16:
        return 1.0  # comfortable headroom
    return 0.6  # vastly oversized


def _use_case_adjust(m: ModelEntry, cls: Classification) -> float:
    adj = 0.0
    if cls.task_type.value in m.ideal_use_cases:
        adj += _IDEAL_BOOST
    if cls.task_type.value in m.avoid_use_cases:
        adj -= _AVOID_PENALTY
    return adj


def score_models(
    eligible: list[ModelEntry], cls: Classification, weights: dict[str, float]
) -> list[dict]:
    """Score + rank eligible models. Returns rows sorted best-first."""
    rows = []
    for m in eligible:
        cap = _capability_match(m, cls)
        cost = _COST_FIT[cls.complexity][m.pricing_tier]
        lat = _LAT_FIT[cls.complexity][m.latency_tier]
        ctx = _context_fit(m, cls)
        adj = _use_case_adjust(m, cls)
        dep = _DEPRECATION_PENALTY if m.deprecation_status is DeprecationStatus.deprecated else 0.0
        score = (
            weights["w_cap"] * cap
            + weights["w_cost"] * cost
            + weights["w_lat"] * lat
            + weights["w_ctx"] * ctx
            + adj
            - dep
        )
        rows.append(
            {
                "model": m.key,
                "provider": m.provider,
                "model_id": m.model_id,
                "pricing_tier": m.pricing_tier.value,
                "terms": {
                    "cap": round(cap, 2),
                    "cost": round(cost, 2),
                    "lat": round(lat, 2),
                    "ctx": round(ctx, 2),
                    "adj": round(adj, 2),
                    "dep": round(dep, 2),
                },
                "score": round(score, 3),
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def pick_fallback(
    ranked: list[dict], models_by_key: dict[str, ModelEntry], eligible_ids: set[str]
) -> dict | None:
    """Fallback selection (ROUTING_RULES.md §5)."""
    if not ranked:
        return None
    rec = models_by_key[ranked[0]["model"]]
    # 1. recommendation's declared fallback list, first eligible entry
    for fb_id in rec.fallback:
        for row in ranked[1:]:
            if row["model_id"] == fb_id and row["model_id"] in eligible_ids:
                return row
    # 2. best remaining that differs meaningfully (provider or lower pricing tier)
    tiers = list(PricingTier)
    for row in ranked[1:]:
        cand = models_by_key[row["model"]]
        if cand.provider != rec.provider or tiers.index(cand.pricing_tier) < tiers.index(
            rec.pricing_tier
        ):
            return row
    # 3. any second-best at all
    return ranked[1] if len(ranked) > 1 else None


def route(
    models: list[ModelEntry],
    cls: Classification,
    base_weights: dict[str, float] | None = None,
    prefer: str | None = None,
) -> dict:
    """Full routing pass: filter -> weight -> score -> recommend + fallback."""
    weights, shifts = weights_for(cls, base_weights, prefer)
    eligible, excluded = eligibility(models, cls)
    models_by_key = {m.key: m for m in models}

    if not eligible:
        # recommend the manual-agent entry if present (ROUTING_RULES.md §2)
        manual = next((m for m in models if m.provider == "manual"), None)
        return {
            "weights": weights,
            "weight_shifts": shifts,
            "excluded": excluded,
            "scores": [],
            "recommendation": None,
            "fallback": None,
            "manual_suggestion": manual.key if manual else None,
        }

    ranked = score_models(eligible, cls, weights)
    eligible_ids = {m.model_id for m in eligible}
    fallback = pick_fallback(ranked, models_by_key, eligible_ids)
    return {
        "weights": weights,
        "weight_shifts": shifts,
        "excluded": excluded,
        "scores": ranked,
        "recommendation": ranked[0],
        "fallback": fallback,
        "manual_suggestion": None,
    }
