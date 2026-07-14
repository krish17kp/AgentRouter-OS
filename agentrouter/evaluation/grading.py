"""100-point master grade + release gates (program §6, §7).

Each dimension carries the program's weight. A dimension is either *measured*
(has a 0..1 score) or *pending* (evaluator not yet wired). We NEVER rescale
away pending work: the scorecard reports achieved points, possible-measured
points, and the full 100 separately, so a partial run cannot masquerade as a
finished one. Release gates override the headline number.
"""

from __future__ import annotations

from .metrics import classification_metrics
from .schema import EvaluationCase

# program §7 dimension weights (sum = 100)
DIMENSION_WEIGHTS = {
    "classification": 30,
    "routing": 25,
    "safety": 15,
    "cli_platform": 10,
    "provider_registry": 8,
    "feedback_storage": 7,
    "performance": 5,
}

# within classification (30), the sub-weights from §6.1 (sum = 30)
_CLASS_SUBWEIGHTS = {
    "task_type": 10,
    "risk": 7,
    "complexity": 4,
    "tools": 4,
    "output": 2,
    "context": 2,
    "approval": 1,
}


def _classification_score(m: dict) -> tuple[float, dict]:
    """0..1 classification score + the per-sub-dimension detail."""
    detail = {}
    total = 0.0
    for dim, w in _CLASS_SUBWEIGHTS.items():
        if dim == "tools":
            s = m["tools"]["f1"]
        else:
            s = m[dim]["accuracy"]
        detail[dim] = {"weight": w, "score": s}
        total += w * s
    return total / sum(_CLASS_SUBWEIGHTS.values()), detail


def grade(cases: list[EvaluationCase], classify_fn=None, *, measure_all: bool = False) -> dict:
    """Grade a case list.

    Classification is always measured. The remaining dimensions
    (routing/safety/cli_platform/provider_registry/feedback_storage/performance)
    are declared *pending* and contribute 0 achieved points UNLESS ``measure_all``
    is set, in which case their real evaluators run and they become *measured*.
    Default (``measure_all=False``) is byte-for-byte the classification-only build:
    pending work is never rescaled away, so a partial run cannot masquerade as a
    finished one.
    """
    from ..classifier import classify

    resolved_classify = classify_fn or classify
    m = classification_metrics(cases, resolved_classify)
    class_score, class_detail = _classification_score(m)

    measured = _measure_dimensions(cases, resolved_classify) if measure_all else {}

    dimensions = {}
    for name, weight in DIMENSION_WEIGHTS.items():
        if name == "classification":
            dimensions[name] = {
                "weight": weight,
                "status": "measured",
                "score": round(class_score, 4),
                "achieved": round(weight * class_score, 3),
                "detail": class_detail,
            }
        elif name in measured:
            result = measured[name]
            dimensions[name] = {
                "weight": weight,
                "status": "measured",
                "score": round(result["score"], 4),
                "achieved": round(weight * result["score"], 3),
                "detail": result["detail"],
            }
        else:
            dimensions[name] = {
                "weight": weight,
                "status": "pending",
                "score": None,
                "achieved": 0.0,
            }

    measured_weight = sum(d["weight"] for d in dimensions.values() if d["status"] == "measured")
    achieved = sum(d["achieved"] for d in dimensions.values())
    grade_of_measured = round(100 * achieved / measured_weight, 2) if measured_weight else 0.0

    gates = _release_gates(m, class_score)
    if measured:
        gates.update(_extended_gates(measured))
    return {
        "n_cases": len(cases),
        "dimensions": dimensions,
        "achieved_points": round(achieved, 2),
        "possible_measured_points": measured_weight,
        "grade_over_100": round(achieved, 2),  # unmeasured dims count as 0 (honest)
        "grade_of_measured": grade_of_measured,  # rescaled to measured-only (context)
        "classification": m,
        "release_gates": gates,
        "release_ready": all(gates.values()),
    }


def _measure_dimensions(cases: list[EvaluationCase], classify_fn) -> dict:
    """Run the real per-dimension evaluators. Each value is {"score", "detail"}."""
    from .evaluators import (
        evaluate_feedback,
        evaluate_performance,
        evaluate_platform,
        evaluate_provider,
        evaluate_routing,
        evaluate_safety,
        load_seed_models,
    )

    models = load_seed_models()
    return {
        "routing": evaluate_routing(cases, models, classify_fn),
        "safety": evaluate_safety(cases, classify_fn),
        "cli_platform": evaluate_platform(),
        "provider_registry": evaluate_provider(models),
        "feedback_storage": evaluate_feedback(),
        "performance": evaluate_performance(models, classify_fn=classify_fn),
    }


def _extended_gates(measured: dict) -> dict:
    """§7 gates unlocked by the routing/safety evaluators. Additive — never
    weakens the classification-only gates."""
    return {
        "high_risk_gated==1.00": measured["safety"]["score"] == 1.0,
        # command.md P13 requires >=0.95; current value is a declared proxy (no gold
        # routing target yet — see P5), so a pass here is proxy-level, not gold-verified.
        "synthetic_routing_top1>=0.95": measured["routing"]["score"] >= 0.95,
    }


def _release_gates(m: dict, class_score: float) -> dict:
    """The subset of §7 gates evaluable from a classification-only run."""
    hrr = m.get("high_risk_recall")
    return {
        "task_type_macro_f1>=0.90": m["task_type"]["macro_f1"] >= 0.90,
        "high_risk_recall==1.00": hrr == 1.0,
        "approval_accuracy==1.00": m["approval"]["accuracy"] == 1.0,
        "tool_needs_f1>=0.90": m["tools"]["f1"] >= 0.90,
        "context_band_accuracy>=0.90": m["context"]["accuracy"] >= 0.90,
    }
