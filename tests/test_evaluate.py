"""Tests for the evaluation framework itself (Phase 1)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentrouter import evaluate as ev

runner = CliRunner()


class _FakePred:
    """Stand-in for a Classification with the .value-bearing enum fields."""

    class _V:
        def __init__(self, v):
            self.value = v

    def __init__(self, task_type, complexity, risk, output, context, approval, tools):
        self.task_type = self._V(task_type)
        self.complexity = self._V(complexity)
        self.risk = self._V(risk)
        self.output_type = self._V(output)
        self.context_band = self._V(context)
        self.approval_level = self._V(approval)
        self.tool_needs = tools


def _perfect_classify(prompt):
    # maps a known prompt to its exactly-correct labels
    return _FakePred(
        "coding",
        "high",
        "high",
        "code+tests",
        "medium",
        "human-approval-required",
        ["file-edit", "shell"],
    )


def _wrong_classify(prompt):
    return _FakePred("writing", "low", "low", "text", "small", "auto", [])


_GOLD_ONE = [
    {
        "id": "t-1",
        "prompt": "Refactor the payment module and add unit tests",
        "task_type": ["coding"],
        "complexity": ["high"],
        "risk": ["high"],
        "output_type": ["code+tests"],
        "tools": ["file-edit", "shell"],
        "context_band": ["medium"],
    }
]


def test_perfect_prediction_scores_100():
    r = ev.grade_cases(_GOLD_ONE, classify_fn=_perfect_classify)
    assert r["overall_grade"] == 100.0
    assert r["failures"] == []
    assert r["task_type"]["accuracy"] == 1.0
    assert r["tools"]["f1"] == 1.0
    assert r["risk"]["high_risk_recall"] == 1.0
    assert r["release_thresholds"]["high_risk_recall==1.00"] is True


def test_all_wrong_prediction_flags_every_dimension():
    r = ev.grade_cases(_GOLD_ONE, classify_fn=_wrong_classify)
    assert r["overall_grade"] < 20
    assert len(r["failures"]) == 1
    failed_dims = {fd["dim"] for fd in r["failures"][0]["failed"]}
    assert failed_dims == {
        "task_type",
        "complexity",
        "risk",
        "output",
        "context",
        "approval",
        "tools",
    }


def test_acceptable_set_counts_as_correct():
    gold = [
        {
            "id": "a",
            "prompt": "x",
            "task_type": ["coding", "reasoning"],
            "complexity": ["medium", "high"],
            "risk": ["low"],
        }
    ]
    r = ev.grade_cases(gold, classify_fn=_perfect_classify)  # predicts coding/high/high
    # coding in {coding,reasoning} -> correct; high in {medium,high} -> correct
    assert r["task_type"]["accuracy"] == 1.0
    assert r["complexity"]["accuracy"] == 1.0
    # risk high not in {low} -> wrong
    assert r["risk"]["accuracy"] == 0.0


def test_tool_micro_prf_partial_overlap():
    gold = [
        {
            "id": "a",
            "prompt": "x",
            "task_type": ["coding"],
            "complexity": ["low"],
            "risk": ["low"],
            "tools": ["file-edit", "shell"],
        }
    ]

    def half(_):
        return _FakePred("coding", "low", "low", "code", "small", "auto", ["file-edit"])

    r = ev.grade_cases(gold, classify_fn=half)
    # tp=1 (file-edit), fp=0, fn=1 (shell) -> P=1.0 R=0.5 F1=0.667
    assert r["tools"]["precision"] == 1.0
    assert r["tools"]["recall"] == 0.5
    assert round(r["tools"]["f1"], 3) == 0.667


def test_approval_derived_from_risk():
    # approval gold is derived from risk; predicting the matching approval passes
    gold = [
        {"id": "a", "prompt": "x", "task_type": ["coding"], "complexity": ["low"], "risk": ["high"]}
    ]
    r = ev.grade_cases(gold, classify_fn=_perfect_classify)  # approval=human-approval-required
    assert r["approval"]["accuracy"] == 1.0


def test_empty_tools_expected_and_predicted_is_exact():
    gold = [
        {
            "id": "a",
            "prompt": "x",
            "task_type": ["writing"],
            "complexity": ["low"],
            "risk": ["low"],
            "tools": [],
        }
    ]
    r = ev.grade_cases(gold, classify_fn=_wrong_classify)  # writing, no tools
    assert r["tools"]["exact_set_accuracy"] == 1.0
    assert r["tools"]["f1"] == 1.0  # no tokens on either side -> perfect by convention


def test_load_real_gold_and_grade_runs():
    gold_path = Path("benchmarks") / "classifier_gold_v1.yaml"
    cases = ev.load_gold(gold_path)
    assert len(cases) >= 150
    r = ev.grade_cases(cases)  # uses the real classifier
    assert 0 <= r["overall_grade"] <= 100
    assert r["n_cases"] == len(cases)


def test_duplicate_ids_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "cases:\n"
        "  - {id: dup, prompt: a, task_type: [coding], complexity: [low], risk: [low]}\n"
        "  - {id: dup, prompt: b, task_type: [coding], complexity: [low], risk: [low]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ev.GoldError):
        ev.load_gold(bad)


def test_write_artifacts_creates_three_files(tmp_path):
    r = ev.grade_cases(_GOLD_ONE, classify_fn=_wrong_classify)
    paths = ev.write_artifacts(r, tmp_path)
    names = {p.name for p in paths}
    assert names == {"evaluation.json", "evaluation.md", "failures.csv"}
    assert all(p.exists() for p in paths)
    assert "Classifier Evaluation Report" in (tmp_path / "evaluation.md").read_text(
        encoding="utf-8"
    )


# --- CLI command --------------------------------------------------------------


def test_cli_evaluate_json_runs(tmp_path):
    from agentrouter.cli import app

    r = runner.invoke(app, ["evaluate", "--json", "--out-dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    report = json.loads(r.output[r.output.index("{"):])
    assert 0 <= report["overall_grade"] <= 100
    assert report["n_cases"] >= 150
    assert (tmp_path / "evaluation.json").exists()


def test_cli_evaluate_human_output(tmp_path):
    from agentrouter.cli import app

    r = runner.invoke(app, ["evaluate", "--no-artifacts"])
    assert r.exit_code == 0, r.output
    assert "Overall grade" in r.output
    assert "Release thresholds" in r.output


def test_cli_evaluate_missing_gold_exits_3(tmp_path):
    from agentrouter.cli import app

    r = runner.invoke(app, ["evaluate", "--gold", str(tmp_path / "nope.yaml"), "--no-artifacts"])
    assert r.exit_code == 3
    assert "Benchmark error" in r.output


def test_cli_evaluate_meets_release_thresholds():
    """The shipped gold benchmark must keep the classifier release-ready."""
    from agentrouter.cli import app

    r = runner.invoke(app, ["evaluate", "--json", "--no-artifacts"])
    report = json.loads(r.output[r.output.index("{"):])
    assert report["release_ready"], report["release_thresholds"]
