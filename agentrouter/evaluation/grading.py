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


def grade(cases: list[EvaluationCase], classify_fn=None) -> dict:
    """Grade a case list. Only classification is measured this build; other
    dimensions are declared pending and contribute 0 achieved points until their
    evaluators land (routing/safety/etc.)."""
    from ..classifier import classify

    m = classification_metrics(cases, classify_fn or classify)
    class_score, class_detail = _classification_score(m)

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
