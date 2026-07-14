"""Tests for the Phase P6 per-dimension evaluators and their wiring into grade().

Each evaluator is checked for a bounded 0..1 score and sensible detail over a
small hand-built case list. grade(measure_all=True) is checked for measured
status, a higher over-100 than the classification-only baseline, and that no
existing release gate was weakened.
"""

from __future__ import annotations

from agentrouter.evaluation.evaluators import (
    evaluate_feedback,
    evaluate_performance,
    evaluate_platform,
    evaluate_provider,
    evaluate_routing,
    evaluate_safety,
    load_seed_models,
)
from agentrouter.evaluation.grading import grade
from agentrouter.evaluation.schema import (
    EvaluationCase,
    ExpectedClassification,
    RoutingExpectation,
    SafetyExpectation,
)


def _cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            id="high1",
            dataset="d",
            task="Rotate the production API keys and update the secrets store",
            expected=ExpectedClassification(risks=["high"]),
            safety=SafetyExpectation(must_require_human_approval=True),
        ),
        EvaluationCase(
            id="write1",
            dataset="d",
            task="Write a blog post about our API launch",
        ),
        EvaluationCase(
            id="code1",
            dataset="d",
            task="Refactor the payment module and add unit tests",
            routing=RoutingExpectation(minimum_ability={"coding": 8}),
        ),
    ]


def _bounded(result: dict) -> None:
    assert 0.0 <= result["score"] <= 1.0
    assert isinstance(result["detail"], dict)


# --- individual evaluators -------------------------------------------------


def test_routing_evaluator_bounded_and_declares_measurement():
    r = evaluate_routing(_cases(), load_seed_models())
    _bounded(r)
    assert r["detail"]["n_gold"] == 1
    assert r["detail"]["n_proxy"] == 2
    assert r["detail"]["measurement"] == "mixed"
    assert 0.0 <= r["detail"]["recommendation_coverage"] <= 1.0


def test_routing_recommendation_coverage_is_full_with_manual_fallback():
    r = evaluate_routing(_cases(), load_seed_models())
    # the always-eligible manual model guarantees a recommendation per case
    assert r["detail"]["recommendation_coverage"] == 1.0


def test_safety_evaluator_gates_high_risk():
    r = evaluate_safety(_cases())
    _bounded(r)
    # the gold high-risk case plus any case the classifier judges high risk
    assert r["detail"]["high_risk_cases"] >= 1
    assert r["detail"]["correctly_gated"] == r["detail"]["high_risk_cases"]
    assert r["detail"]["high_risk_recall"] == 1.0
    assert r["score"] == 1.0


def test_platform_evaluator_finds_expected_commands():
    r = evaluate_platform()
    _bounded(r)
    assert r["score"] == 1.0
    assert r["detail"]["missing"] == []
    assert "route" in r["detail"]["commands_found"]
    assert "registry" in r["detail"]["groups_found"]


def test_provider_evaluator_seed_registry_complete():
    r = evaluate_provider()
    _bounded(r)
    assert r["detail"]["n_models"] >= 1
    assert r["score"] == 1.0  # seed registry ships complete metadata
    assert r["detail"]["failures"] == []


def test_provider_evaluator_flags_placeholder_metadata():
    models = list(load_seed_models())
    broken = models[0].model_copy(update={"source": "unknown", "last_updated": None})
    r = evaluate_provider([broken, *models[1:]])
    assert r["score"] < 1.0
    assert any("provenance.source" in f["missing"] for f in r["detail"]["failures"])


def test_feedback_evaluator_roundtrips_in_tmp_home():
    r = evaluate_feedback()
    _bounded(r)
    assert r["score"] == 1.0
    assert all(r["detail"]["checks"].values())


def test_performance_evaluator_records_medians():
    r = evaluate_performance()
    _bounded(r)
    assert r["detail"]["classify_median_ms"] >= 0.0
    assert r["detail"]["route_median_ms"] >= 0.0
    assert r["detail"]["classify_threshold_ms"] == 50.0


# --- grade() wiring --------------------------------------------------------


def test_grade_measure_all_marks_dimensions_measured():
    r = grade(_cases(), measure_all=True)
    for dim in (
        "routing",
        "safety",
        "cli_platform",
        "provider_registry",
        "feedback_storage",
        "performance",
    ):
        assert r["dimensions"][dim]["status"] == "measured"
        assert r["dimensions"][dim]["score"] is not None


def test_grade_over_100_increases_vs_classification_only_baseline():
    cases = _cases()
    baseline = grade(cases)
    full = grade(cases, measure_all=True)
    assert full["grade_over_100"] > baseline["grade_over_100"]


def test_default_grade_keeps_pending_dimensions():
    # measure_all defaults False -> old behavior preserved (no rescaling of pending)
    r = grade(_cases())
    assert r["dimensions"]["routing"]["status"] == "pending"
    assert r["dimensions"]["performance"]["achieved"] == 0.0


def test_no_existing_gate_weakened_and_high_risk_recall_still_required():
    r = grade(_cases(), measure_all=True)
    gates = r["release_gates"]
    # the classification-only gates are still present and still strict
    assert "high_risk_recall==1.00" in gates
    assert gates["high_risk_recall==1.00"] is True
    assert "approval_accuracy==1.00" in gates
    # new gates are additive
    assert "high_risk_gated==1.00" in gates
    assert "synthetic_routing_top1>=0.95" in gates


def test_extended_gates_do_not_replace_baseline_gate_keys():
    baseline_gates = set(grade(_cases())["release_gates"])
    full_gates = set(grade(_cases(), measure_all=True)["release_gates"])
    assert baseline_gates.issubset(full_gates)
