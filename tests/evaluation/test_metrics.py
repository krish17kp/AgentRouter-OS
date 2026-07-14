"""Tests for classification metrics over EvaluationCases."""

from agentrouter.evaluation.metrics import classification_metrics
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification


class _Pred:
    class _V:
        def __init__(self, v):
            self.value = v

    def __init__(self, tt, cx, rk, out, ctx, appr, tools):
        self.task_type = self._V(tt)
        self.complexity = self._V(cx)
        self.risk = self._V(rk)
        self.output_type = self._V(out)
        self.context_band = self._V(ctx)
        self.approval_level = self._V(appr)
        self.tool_needs = tools


def _case(**expected):
    return EvaluationCase(
        id="t1",
        dataset="d",
        task="Refactor the payment module and add unit tests",
        expected=ExpectedClassification(**expected),
    )


def _perfect(_):
    return _Pred(
        "coding",
        "high",
        "high",
        "code+tests",
        "medium",
        "human-approval-required",
        ["file-edit", "shell"],
    )


def _wrong(_):
    return _Pred("writing", "low", "low", "text", "small", "auto", [])


def test_perfect_prediction_scores_all_dimensions():
    m = classification_metrics(
        [_case(task_types=["coding"], risks=["high"], required_tools=["file-edit", "shell"])],
        classify_fn=_perfect,
    )
    assert m["task_type"]["accuracy"] == 1.0
    assert m["tools"]["f1"] == 1.0
    assert m["high_risk_recall"] == 1.0
    assert m["failures"] == []


def test_wrong_prediction_flags_failures():
    m = classification_metrics(
        [_case(task_types=["coding"], risks=["high"], required_tools=["file-edit", "shell"])],
        classify_fn=_wrong,
    )
    assert m["task_type"]["accuracy"] == 0.0
    assert len(m["failures"]) == 1
    dims = {fd["dim"] for fd in m["failures"][0]["failed"]}
    assert {"task_type", "risk", "tools"} <= dims


def test_acceptable_set_counts_as_correct():
    m = classification_metrics([_case(task_types=["coding", "reasoning"])], classify_fn=_perfect)
    assert m["task_type"]["accuracy"] == 1.0


def test_empty_expected_dimension_is_skipped():
    # only task_types provided -> complexity dimension has zero graded pairs
    m = classification_metrics([_case(task_types=["coding"])], classify_fn=_perfect)
    assert m["complexity"]["n"] == 0


def test_confusion_matrix_present():
    m = classification_metrics([_case(task_types=["coding"])], classify_fn=_wrong)
    assert "coding" in m["confusion_task_type"]
