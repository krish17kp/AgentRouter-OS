"""Tests for the 100-point grade + release gates."""

from agentrouter.evaluation.grading import DIMENSION_WEIGHTS, grade
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification


class _Pred:
    class _V:
        def __init__(self, v):
            self.value = v

    def __init__(self):
        self.task_type = self._V("coding")
        self.complexity = self._V("high")
        self.risk = self._V("high")
        self.output_type = self._V("code+tests")
        self.context_band = self._V("medium")
        self.approval_level = self._V("human-approval-required")
        self.tool_needs = ["file-edit", "shell"]


def _perfect(_):
    return _Pred()


def _gold():
    return [
        EvaluationCase(
            id="t1",
            dataset="d",
            task="Refactor the payment module and add unit tests",
            expected=ExpectedClassification(
                task_types=["coding"],
                complexities=["high"],
                risks=["high"],
                output_types=["code+tests"],
                context_bands=["medium"],
                required_tools=["file-edit", "shell"],
                approval_levels=["human-approval-required"],
            ),
        )
    ]


def test_weights_sum_to_100():
    assert sum(DIMENSION_WEIGHTS.values()) == 100


def test_classification_is_measured_others_pending():
    r = grade(_gold(), classify_fn=_perfect)
    assert r["dimensions"]["classification"]["status"] == "measured"
    assert r["dimensions"]["routing"]["status"] == "pending"


def test_perfect_classification_scores_measured_100():
    r = grade(_gold(), classify_fn=_perfect)
    assert r["grade_of_measured"] == 100.0
    assert r["dimensions"]["classification"]["score"] == 1.0


def test_unmeasured_dims_count_zero_in_over_100():
    # perfect classification = 30 achieved of 100 possible -> grade_over_100 == 30
    r = grade(_gold(), classify_fn=_perfect)
    assert r["grade_over_100"] == 30.0


def test_release_gates_pass_on_perfect():
    r = grade(_gold(), classify_fn=_perfect)
    assert r["release_ready"] is True
    assert r["release_gates"]["high_risk_recall==1.00"] is True
