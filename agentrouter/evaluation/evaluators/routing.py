"""Routing evaluator (§7 routing, weight 25).

Runs the real routing engine on each case's classification and measures top-1
correctness. Where a case carries a ``RoutingExpectation`` (constraint gold) we
check the recommendation against those constraints. Where it does not, we fall
back to a declared PROXY: the recommendation is non-None and the fallback is a
distinct model. The detail states how many cases were gold vs proxy so a reader
never mistakes proxy coverage for verified routing accuracy.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...classifier import classify
from ...engine import route
from ...schema import ModelEntry
from ..schema import EvaluationCase, RoutingExpectation


def _satisfies(model: ModelEntry, rexp: RoutingExpectation) -> tuple[bool, str | None]:
    """Does a recommended model satisfy the case's routing constraints?"""
    for dim, floor in rexp.minimum_ability.items():
        if getattr(model.ability, dim, 0) < floor:
            return False, f"ability.{dim} {getattr(model.ability, dim, 0)} < {floor}"
    if rexp.acceptable_pricing_tiers and model.pricing_tier not in rexp.acceptable_pricing_tiers:
        return False, f"pricing_tier {model.pricing_tier.value} not acceptable"
    if rexp.permitted_providers and model.provider not in rexp.permitted_providers:
        return False, f"provider {model.provider} not permitted"
    if model.model_id in rexp.forbidden_models:
        return False, f"model {model.model_id} is forbidden"
    if rexp.min_context_tokens and model.context_window < rexp.min_context_tokens:
        return False, f"context_window {model.context_window} < {rexp.min_context_tokens}"
    return True, None


def evaluate_routing(
    cases: Sequence[EvaluationCase], models: Sequence[ModelEntry], classify_fn=classify
) -> dict:
    """Fraction of cases whose top-1 recommendation is correct (gold) or sane (proxy)."""
    models = list(models)
    by_key = {m.key: m for m in models}
    n_gold = n_proxy = 0
    passed = 0
    with_recommendation = 0
    failures: list[dict] = []

    for case in cases:
        cls = classify_fn(case.task)
        result = route(models, cls)
        rec = result["recommendation"]
        fb = result["fallback"]
        if rec is not None:
            with_recommendation += 1

        if case.routing is not None:
            n_gold += 1
            if rec is None:
                ok, why = False, "no recommendation"
            else:
                ok, why = _satisfies(by_key[rec["model"]], case.routing)
        else:
            n_proxy += 1
            ok = rec is not None and fb is not None and fb["model"] != rec["model"]
            why = None if ok else "recommendation missing or fallback not distinct"

        if ok:
            passed += 1
        else:
            failures.append({"id": case.id, "reason": why, "recommendation": rec and rec["model"]})

    n = len(cases)
    score = passed / n if n else 0.0
    return {
        "score": round(score, 4),
        "detail": {
            "n_cases": n,
            "n_gold": n_gold,
            "n_proxy": n_proxy,
            "measurement": "gold" if n_gold and not n_proxy else "proxy" if not n_gold else "mixed",
            "top1": round(score, 4),
            "recommendation_coverage": round(with_recommendation / n, 4) if n else 0.0,
            "proxy_note": (
                "proxy cases scored on: recommendation non-None AND distinct fallback; "
                "NOT verified against a gold routing target"
            ),
            "failures": failures[:20],
        },
    }
