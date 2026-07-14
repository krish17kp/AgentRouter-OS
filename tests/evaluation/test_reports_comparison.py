"""Tests for report writers and baseline comparison."""

from agentrouter.evaluation import comparison, reports
from agentrouter.evaluation.grading import grade
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification


class _Pred:
    class _V:
        def __init__(self, v):
            self.value = v

    def __init__(self, tt="coding", rk="high"):
        self.task_type = self._V(tt)
        self.complexity = self._V("high")
        self.risk = self._V(rk)
        self.output_type = self._V("code+tests")
        self.context_band = self._V("medium")
        self.approval_level = self._V("human-approval-required")
        self.tool_needs = ["file-edit", "shell"]


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


def test_write_reports_creates_expected_files(tmp_path):
    r = grade(_gold(), classify_fn=lambda _: _Pred())
    written = reports.write_reports(r, tmp_path)
    names = {p.name for p in written}
    assert {
        "result.json",
        "scorecard.json",
        "report.md",
        "failures.csv",
        "confusion_task_type.csv",
        "confusion_risk.csv",
    } <= names
    for p in written:
        assert p.exists()


def test_render_markdown_mentions_grade():
    r = grade(_gold(), classify_fn=lambda _: _Pred())
    md = reports.render_markdown(r)
    assert "Grade" in md and "Release gates" in md


def test_comparison_flags_regression():
    good = grade(_gold(), classify_fn=lambda _: _Pred())
    bad = grade(_gold(), classify_fn=lambda _: _Pred(tt="writing"))
    cmp = comparison.compare(good, bad)
    assert cmp["has_critical_regression"] is True
    assert any(r["dimension"] == "classification" for r in cmp["regressions"])


def test_comparison_no_regression_when_identical():
    r = grade(_gold(), classify_fn=lambda _: _Pred())
    cmp = comparison.compare(r, r)
    assert cmp["has_critical_regression"] is False
    assert cmp["regressions"] == []
