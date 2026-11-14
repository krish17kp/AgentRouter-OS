"""TASK-009: held-out context-band generalization and leakage controls."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import yaml

from agentrouter.evaluation import context_bands
from agentrouter.evaluation.grading import grade
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification
from agentrouter.schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    OutputType,
    TaskType,
)


def _gold_prompts() -> list[str]:
    raw = yaml.safe_load(
        context_bands.gold_path("classifier_gold_v1.yaml").read_text(encoding="utf-8")
    )
    return [case["prompt"] for case in raw["cases"]]


def _test_string_literals() -> list[str]:
    strings: list[str] = []
    for path in Path(__file__).parent.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings.extend(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and len(node.value.split()) >= 3
        )
    return strings


def test_development_and_holdout_are_separate_balanced_splits():
    development = context_bands.load_development()
    holdout = context_bands.load_holdout()
    assert len(development) == 24
    assert len(holdout) == 45
    assert {case.id for case in development}.isdisjoint(case.id for case in holdout)
    assert Counter(case.context_band for case in holdout) == {
        "small": 15,
        "medium": 15,
        "large": 15,
    }
    assert context_bands.REQUIRED_CATEGORIES <= {case.category for case in holdout}


def test_frozen_holdout_checksum_is_locked(tmp_path):
    assert context_bands.load_holdout()
    assert len(context_bands.HOLDOUT_SHA256) == 64
    source = context_bands.gold_path(context_bands.HOLDOUT_FILE).read_text(encoding="utf-8")
    crlf_copy = tmp_path / "holdout-crlf.yaml"
    crlf_copy.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
    assert context_bands._sha256(crlf_copy) == context_bands.HOLDOUT_SHA256


def test_holdout_has_no_exact_or_near_leakage():
    development = context_bands.load_development()
    holdout = context_bands.load_holdout()
    leaks = context_bands.cross_split_leaks(
        holdout,
        {
            "development": [case.prompt for case in development],
            "classifier-gold": _gold_prompts(),
            "python-test-literals": _test_string_literals(),
        },
    )
    assert leaks == []


def test_metrics_are_deterministic_bounded_and_include_intervals():
    cases = context_bands.load_development()
    expected = {case.prompt: case.context_band for case in cases}
    first = context_bands.score(cases, expected.__getitem__)
    second = context_bands.score(cases, expected.__getitem__)
    assert first == second
    assert first["accuracy"] == first["macro_f1"] == 1.0
    assert all(value == 1.0 for value in first["per_band_recall"].values())
    assert first["accuracy_ci95"][0] <= first["accuracy"] <= first["accuracy_ci95"][1]
    assert first["macro_f1_bootstrap_ci95"] == [1.0, 1.0]
    assert all(len(interval) == 2 for interval in first["per_band_recall_ci95"].values())


def test_current_classifier_meets_separate_development_contract():
    report = context_bands.score(context_bands.load_development())
    assert report["accuracy"] >= 0.90
    assert report["macro_f1"] >= 0.90
    assert min(report["per_band_recall"].values()) >= 0.85


def test_pre_change_and_current_use_the_same_frozen_holdout():
    report = context_bands.evaluate_generalization()
    assert report["holdout_sha256"] == context_bands.HOLDOUT_SHA256
    assert report["pre_task004_holdout"]["n"] == report["current_holdout"]["n"] == 45
    assert report["pre_task004_holdout"]["accuracy"] == 0.4889
    assert report["pre_task004_holdout"]["macro_f1"] == 0.4453
    assert report["pre_task004_holdout"]["per_band_recall"] == {
        "small": 0.9333,
        "medium": 0.0667,
        "large": 0.4667,
    }
    assert report["delta"]["accuracy"] == round(
        report["current_holdout"]["accuracy"] - report["pre_task004_holdout"]["accuracy"],
        4,
    )


def test_historical_comparator_does_not_call_live_classifier_helpers(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("historical comparator called mutable production logic")

    monkeypatch.setattr(context_bands.classifier, "_band", unexpected)
    monkeypatch.setattr(context_bands.classifier, "_hit", unexpected)
    monkeypatch.setattr(context_bands.classifier, "_matcher", unexpected)

    assert context_bands.legacy_pre_task004_band("review this existing repository") == "medium"
    assert context_bands.legacy_pre_task004_band("draft a haiku") == "small"


def _PerfectPrediction():
    return Classification(
        task_type=TaskType.coding,
        complexity=Level.high,
        risk=Level.high,
        context_tokens=12_000,
        context_band=ContextBand.medium,
        output_type=OutputType.code_tests,
        approval_level=ApprovalLevel.human_approval_required,
        tool_needs=["file-edit", "shell"],
    )


def _perfect_case() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            id="perfect",
            dataset="test",
            task="Synthetic perfect prediction",
            expected=ExpectedClassification(
                task_types=["coding"],
                complexities=["high"],
                risks=["high"],
                output_types=["code+tests"],
                context_bands=["medium"],
                approval_levels=["human-approval-required"],
                required_tools=["file-edit", "shell"],
            ),
        )
    ]


def test_holdout_replaces_only_the_existing_context_gate():
    baseline = grade(_perfect_case(), classify_fn=lambda _: _PerfectPrediction(), measure_all=True)
    failing_holdout = {
        "current_holdout": {"accuracy": 0.5},
        "pre_task004_holdout": {"accuracy": 0.4},
    }
    held_out = grade(
        _perfect_case(),
        classify_fn=lambda _: _PerfectPrediction(),
        measure_all=True,
        context_band_generalization=failing_holdout,
    )
    context_gate = "context_band_accuracy>=0.90"
    assert baseline["release_gates"][context_gate] is True
    assert held_out["release_gates"][context_gate] is False
    assert {
        key: value for key, value in baseline["release_gates"].items() if key != context_gate
    } == {key: value for key, value in held_out["release_gates"].items() if key != context_gate}


def test_current_holdout_metric_drives_unchanged_threshold():
    report = context_bands.evaluate_generalization()
    accuracy = report["current_holdout"]["accuracy"]
    result = grade(
        _perfect_case(),
        classify_fn=lambda _: _PerfectPrediction(),
        context_band_generalization=report,
    )
    assert result["release_gates"]["context_band_accuracy>=0.90"] is (accuracy >= 0.90)
