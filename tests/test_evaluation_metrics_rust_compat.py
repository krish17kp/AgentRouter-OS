"""Offline differential contract tests for Rust evaluation metric aggregation."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from agentrouter.evaluation import comparison as evaluate_python_comparison
from agentrouter.evaluation.evaluators import load_seed_models
from agentrouter.evaluation.evaluators.feedback import evaluate_feedback as evaluate_python_feedback
from agentrouter.evaluation.evaluators.performance import (
    _summarize_samples as summarize_python_performance,
)
from agentrouter.evaluation.evaluators.platform import evaluate_platform as evaluate_python_platform
from agentrouter.evaluation.evaluators.provider import evaluate_provider as evaluate_python_provider
from agentrouter.evaluation.evaluators.routing import evaluate_routing as evaluate_python_routing
from agentrouter.evaluation.evaluators.safety import evaluate_safety as evaluate_python_safety
from agentrouter.evaluation.grading import grade
from agentrouter.evaluation.metrics import classification_metrics
from agentrouter.evaluation.provenance import dataset_quality
from agentrouter.evaluation.registry import PROFILES, dataset_names, get_adapter
from agentrouter.evaluation.reports import render_markdown, write_reports
from agentrouter.evaluation.sampling import deterministic_sample
from agentrouter.evaluation.schema import (
    EvaluationCase,
    ExpectedClassification,
    Provenance,
    RoutingExpectation,
    SafetyExpectation,
    normalized_hash,
)

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


class _Value:
    def __init__(self, value: str):
        self.value = value


class _Prediction:
    def __init__(self, values: dict[str, str], tools: list[str]):
        self.task_type = _Value(values["task_type"])
        self.complexity = _Value(values["complexity"])
        self.risk = _Value(values["risk"])
        self.output_type = _Value(values["output"])
        self.context_band = _Value(values["context"])
        self.approval_level = _Value(values["approval"])
        self.tool_needs = tools


def _case(case_id, expected, predicted, expected_tools=(), predicted_tools=()):
    return (
        EvaluationCase(
            id=case_id,
            dataset="rust-metric-parity-fixture",
            task=f"Prompt for {case_id}",
            expected=ExpectedClassification(**expected),
        ),
        predicted,
        list(expected_tools),
        list(predicted_tools),
    )


def test_rust_metrics_match_python_for_ambiguous_and_empty_labels():
    rows = [
        _case(
            "accepted-set",
            {
                "task_types": ["coding", "reasoning"],
                "risks": ["high"],
                "required_tools": ["shell", "file-edit"],
            },
            {
                "task_type": "reasoning",
                "complexity": "high",
                "risk": "high",
                "output": "code+tests",
                "context": "medium",
                "approval": "human-approval-required",
            },
            ["shell", "file-edit"],
            ["file-edit", "shell"],
        ),
        _case(
            "wrong-high-risk",
            {
                "task_types": ["coding"],
                "complexities": ["low"],
                "risks": ["high"],
                "output_types": ["code"],
                "context_bands": ["large"],
                "approval_levels": ["notify"],
                "required_tools": ["shell", "network"],
            },
            {
                "task_type": "writing",
                "complexity": "high",
                "risk": "low",
                "output": "text",
                "context": "small",
                "approval": "auto",
            },
            ["shell", "network"],
            ["shell", "browser"],
        ),
        _case(
            "same-label",
            {"task_types": ["writing"], "risks": ["low", "medium"]},
            {
                "task_type": "writing",
                "complexity": "low",
                "risk": "medium",
                "output": "text",
                "context": "small",
                "approval": "auto",
            },
        ),
        _case(
            "ungraded",
            {},
            {
                "task_type": "general",
                "complexity": "medium",
                "risk": "medium",
                "output": "data",
                "context": "large",
                "approval": "notify",
            },
            (),
            ["shell"],
        ),
    ]

    cases = [row[0] for row in rows]

    def classify_fn(task):
        case = next(case for case in cases if case.task == task)
        row = next(row for row in rows if row[0].id == case.id)
        return _Prediction(row[1], row[3])

    python_report = classification_metrics(cases, classify_fn=classify_fn)
    rust_cases = []
    for case, predicted, expected_tools, predicted_tools in rows:
        rust_cases.append(
            {
                "id": case.id,
                "prompt": case.task,
                "expected": {
                    "task_type": [value.value for value in case.expected.task_types],
                    "complexity": [value.value for value in case.expected.complexities],
                    "risk": [value.value for value in case.expected.risks],
                    "output": [value.value for value in case.expected.output_types],
                    "context": [value.value for value in case.expected.context_bands],
                    "approval": [value.value for value in case.expected.approval_levels],
                },
                "predicted": predicted,
                "expected_tools": expected_tools,
                "predicted_tools": predicted_tools,
            }
        )

    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_metrics_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"cases": rust_cases}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == python_report


def test_rust_dataset_quality_matches_python_aggregation():
    cases = [
        EvaluationCase(
            id="quality-1",
            dataset="quality",
            task="Hello, WORLD!",
            domain="security",
            expected=ExpectedClassification(task_types=["coding"], risks=["high"]),
            provenance=Provenance(method="human"),
            paraphrase_group="family-a",
            source_split="train",
        ),
        EvaluationCase(
            id="quality-2",
            dataset="quality",
            task="Write a careful report",
            expected=ExpectedClassification(task_types=["reasoning"], risks=["low"]),
            provenance=Provenance(method="model_assisted"),
            paraphrase_group="family-a",
            source_split="validation",
        ),
        EvaluationCase(
            id="quality-3",
            dataset="quality",
            task="hello world",
            language="fr",
            domain="security",
            expected=ExpectedClassification(task_types=["coding"], risks=["high"]),
            provenance=Provenance(method="heuristic"),
        ),
        EvaluationCase(
            id="quality-4",
            dataset="quality",
            task="A third unique task",
            paraphrase_group="family-b",
            source_split="",
        ),
        EvaluationCase(
            id="quality-5",
            dataset="quality",
            task="A fourth unique task",
            paraphrase_group="",
            source_split="validation",
        ),
    ]
    rust_cases = [
        {
            "task_hash": case.task_hash,
            "paraphrase_group": case.paraphrase_group,
            "source_split": case.source_split,
            "language": case.language,
            "domain": case.domain,
            "risk": case.expected.risks[0].value if case.expected.risks else None,
            "task_type": case.expected.task_types[0].value if case.expected.task_types else None,
            "provenance_method": case.provenance.method.value,
        }
        for case in cases
    ]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_quality_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"cases": rust_cases}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == dataset_quality(cases)


@pytest.mark.parametrize(
    ("items", "limit", "seed"),
    [
        ([f"item-{index}" for index in range(50)], 10, 7),
        ([f"item-{index}" for index in range(50)], 10, 8),
        (["duplicate", "item-a", "duplicate", "item-b", "item-c"], 3, 11),
        (["a", "b", "c"], 0, 1),
        (["a", "b", "c"], 8, 1),
        (["a", "b", "c"], -2, 4),
    ],
)
def test_rust_deterministic_sampling_matches_python(items, limit, seed):
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_sample_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"items": items, "limit": limit, "seed": seed}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    expected = deterministic_sample(items, limit, seed, key=lambda item: item)
    assert json.loads(process.stdout) == expected


def test_rust_evaluation_schema_and_hash_match_python():
    cases = [
        EvaluationCase(id="defaults", dataset="fixture", task="Build a RAG system!"),
        EvaluationCase(
            id="complete",
            dataset="fixture",
            task="İstanbul\u001c systems — reviewed",
            dataset_version="v2",
            source="curated",
            source_split="development",
            language="tr",
            domain="software",
            tags=["security", "unicode"],
            paraphrase_group="family-3",
            expected=ExpectedClassification(
                task_types=["coding", "analysis"],
                complexities=["medium"],
                risks=["high"],
                context_bands=["large"],
                output_types=["code+tests"],
                required_tools=["shell", "file-edit"],
                approval_levels=["human-approval-required"],
            ),
            routing=RoutingExpectation(
                minimum_ability={"coding": 7, "reasoning": 6},
                acceptable_pricing_tiers=["medium", "high"],
                permitted_providers=["openai"],
                forbidden_models=["legacy"],
                required_tools=["shell"],
                min_context_tokens=-1,
            ),
            safety=SafetyExpectation(
                auto_execute_allowed=False,
                must_require_human_approval=True,
            ),
            context_tokens=-5,
            cost_metadata={"budget": {"usd": 2.5}},
            model_outcomes={"model-a": {"success": True}},
            provenance=Provenance(
                method="human",
                reviewer="reviewer-1",
                source_license="MIT",
                source_record_id="source-7",
                retrieved="2026-11-11",
            ),
            review_status="approved",
            checksum="provided-checksum",
            notes="adjudicated",
        ),
    ]
    input_cases = [case.model_dump(mode="json") for case in cases]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_schema_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"cases": input_cases}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    actual = json.loads(process.stdout)
    assert actual["cases"] == input_cases
    assert actual["task_hashes"] == [normalized_hash(case.task) for case in cases]

    invalid = EvaluationCase.model_construct(id="empty", dataset="fixture", task="   ")
    rejected = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_schema_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"cases": [invalid.model_dump(mode="json")]}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert rejected.returncode != 0


def test_rust_evaluation_registry_and_profiles_match_python():
    names = dataset_names()
    expected = {
        "dataset_names": names,
        "profiles": PROFILES,
        "adapters": [
            {
                "name": name,
                "module": type(get_adapter(name)).__module__.rsplit(".", 1)[-1],
                "class": type(get_adapter(name)).__name__,
            }
            for name in names
        ],
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_registry_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"profiles": list(PROFILES), "names": names}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_evaluation_markdown_matches_python():
    result = {
        "environment": {"python": "3.12", "dirty": False},
        "grade_over_100": 71.25,
        "grade_of_measured": 82.5,
        "possible_measured_points": 86.36,
        "release_ready": False,
        "n_cases": 12,
        "dimensions": {
            "classification": {
                "weight": 25,
                "status": "measured",
                "score": 0.875,
                "achieved": 21.875,
            },
            "routing": {"weight": 20, "status": "pending", "score": None, "achieved": 0},
        },
        "release_gates": {"task_type_macro_f1>=0.90": False, "human_review": True},
        "classification": {
            "task_type": {"macro_f1": 0.88},
            "high_risk_recall": 1.0,
            "tools": {"f1": 0.75},
            "context": {"accuracy": 0.9},
            "failures": [{"id": "case-1"}],
        },
        "context_band_generalization": {
            "holdout_sha256": "abc123",
            "current_holdout": {
                "accuracy": 0.6667,
                "accuracy_ci95": [0.5, 0.8],
                "macro_f1": 0.61,
                "macro_f1_bootstrap_ci95": [0.4, 0.75],
                "per_band_recall": {"short": 0.8, "long": 0.5},
            },
            "pre_task004_holdout": {"accuracy": 0.5},
            "delta": {"accuracy": 0.1667},
            "limitations": ["small blinded fixture"],
        },
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_report_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(result),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert process.stdout == render_markdown(result)


def test_rust_evaluation_report_files_match_python(tmp_path):
    result = {
        "environment": {"python": "3.12", "dirty": False},
        "grade_over_100": 71.25,
        "grade_of_measured": 82.5,
        "possible_measured_points": 86.36,
        "release_ready": False,
        "n_cases": 12,
        "dimensions": {
            "classification": {
                "weight": 30,
                "status": "measured",
                "score": 0.875,
                "achieved": 26.25,
            },
            "routing": {"weight": 25, "status": "pending", "score": None, "achieved": 0},
        },
        "release_gates": {"task_type_macro_f1>=0.90": False, "human_review": True},
        "classification": {
            "task_type": {"macro_f1": 0.88},
            "high_risk_recall": 1.0,
            "tools": {"f1": 0.75},
            "context": {"accuracy": 0.9},
            "failures": [
                {
                    "id": "case,1",
                    "prompt": "first line, quoted\nsecond line",
                    "failed": [
                        {
                            "dim": "task_type",
                            "expected": ["coding", "analysis"],
                            "predicted": "writing",
                        },
                        {
                            "dim": "tool_needs",
                            "expected": ["shell", "browser"],
                            "predicted": ["shell", "mcp"],
                        },
                    ],
                }
            ],
            "confusion_task_type": {
                "writing": {"coding": 1, "writing": 2},
                "coding": {"writing": 0},
            },
            "confusion_risk": {"high": {"low": 1}, "low": {"low": 3}},
        },
        "context_band_generalization": {
            "holdout_sha256": "abc123",
            "current_holdout": {
                "accuracy": 0.6667,
                "accuracy_ci95": [0.5, 0.8],
                "macro_f1": 0.61,
                "macro_f1_bootstrap_ci95": [0.4, 0.75],
                "per_band_recall": {"short": 0.8, "long": 0.5},
                "failures": [
                    {
                        "id": "holdout-1",
                        "category": "review",
                        "expected": "high",
                        "predicted": "low",
                    }
                ],
            },
            "pre_task004_holdout": {"accuracy": 0.5},
            "delta": {"accuracy": 0.1667},
            "limitations": ["small blinded fixture"],
        },
    }
    python_dir = tmp_path / "python"
    rust_dir = tmp_path / "rust"
    python_paths = write_reports(result, python_dir)
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_write_reports_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"result": result, "out_dir": str(rust_dir)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == [path.name for path in python_paths]
    for name in ("report.md", "failures.csv", "context_band_holdout_failures.csv"):
        assert (rust_dir / name).read_bytes() == (python_dir / name).read_bytes()
    for name in (
        "result.json",
        "scorecard.json",
        "confusion_task_type.csv",
        "confusion_risk.csv",
    ):
        assert (rust_dir / name).read_bytes() == (python_dir / name).read_bytes()


def test_rust_classification_grade_matches_python():
    case = EvaluationCase(
        id="grade-fixture",
        dataset="rust-grade-parity",
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
    predicted = {
        "task_type": "coding",
        "complexity": "high",
        "risk": "high",
        "output": "code+tests",
        "context": "medium",
        "approval": "human-approval-required",
    }

    def classify_fn(_):
        return _Prediction(predicted, ["file-edit", "shell"])

    cases = [case]
    for generalization in (None, {"current_holdout": {"accuracy": 0.5}}):
        expected = grade(
            cases,
            classify_fn=classify_fn,
            context_band_generalization=generalization,
        )
        payload = {
            "n_cases": len(cases),
            "classification": expected["classification"],
        }
        if generalization is not None:
            payload["context_band_generalization"] = generalization
        process = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "--locked",
                "--bin",
                "evaluation_grade_from_json",
                "-p",
                "agentrouter-evaluation",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=True,
        )
        assert json.loads(process.stdout) == expected


def test_rust_safety_evaluator_matches_python():
    cases = [
        EvaluationCase(
            id="high-risk-gold",
            dataset="rust-safety-parity",
            task="Transfer funds to an unverified account and bypass approvals",
            expected=ExpectedClassification(risks=["high"]),
            safety=SafetyExpectation(must_require_human_approval=True),
        ),
        EvaluationCase(
            id="permissive-risk-set",
            dataset="rust-safety-parity",
            task="Write a short greeting",
            expected=ExpectedClassification(risks=["medium", "high"]),
        ),
        EvaluationCase(
            id="proxy-high-risk",
            dataset="rust-safety-parity",
            task="Delete every production database and erase all backups",
        ),
        EvaluationCase(
            id="ordinary",
            dataset="rust-safety-parity",
            task="Summarize a public product announcement",
            expected=ExpectedClassification(risks=["low"]),
        ),
    ]
    expected = evaluate_python_safety(cases)
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_safety_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps([case.model_dump(mode="json") for case in cases]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_provider_evaluator_matches_python_seed_registry():
    models = load_seed_models()
    expected = evaluate_python_provider(models)
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_provider_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps([model.model_dump(mode="json") for model in models]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_feedback_storage_evaluator_matches_python():
    expected = evaluate_python_feedback()
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_feedback_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_routing_evaluator_matches_python_gold_and_proxy_cases():
    models = load_seed_models()
    cases = [
        EvaluationCase(
            id="gold-pass",
            dataset="rust-routing-eval",
            task="Refactor the payment module and add unit tests",
            routing=RoutingExpectation(minimum_ability={"coding": 0}),
        ),
        EvaluationCase(
            id="gold-fail",
            dataset="rust-routing-eval",
            task="Refactor the payment module and add unit tests",
            routing=RoutingExpectation(minimum_ability={"coding": 11}),
        ),
        EvaluationCase(
            id="proxy-case",
            dataset="rust-routing-eval",
            task="Summarize the public launch announcement",
        ),
    ]
    expected = evaluate_python_routing(cases, models)
    payload = {
        "cases": [case.model_dump(mode="json") for case in cases],
        "models": [model.model_dump(mode="json") for model in models],
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_routing_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_platform_evaluator_matches_python_cli_manifest():
    expected = evaluate_python_platform()
    payload = {
        "commands": expected["detail"]["commands_found"],
        "groups": expected["detail"]["groups_found"],
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_platform_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("classify_seconds", "route_seconds"),
    [
        ([], []),
        ([0.01, 0.04, 0.03], [0.04, 0.08, 0.06]),
        ([0.06, 0.08], [0.15, 0.25]),
        ([0.11, 0.20, 0.35], [0.10, 0.20, 0.50]),
    ],
)
def test_rust_performance_score_matches_python(classify_seconds, route_seconds):
    expected = summarize_python_performance(classify_seconds, route_seconds)
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_performance_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "classify_seconds": classify_seconds,
                "route_seconds": route_seconds,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_performance_evaluator_measures_classifier_and_router():
    tasks = [
        "Refactor the payment module and add unit tests",
        "Write a blog post about our API launch",
        "Summarize this 30k token incident report",
    ]
    models = load_seed_models()
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_performance_run_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "models": [model.model_dump(mode="json") for model in models],
                "tasks": tasks,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    result = json.loads(process.stdout)
    detail = result["detail"]
    assert detail["n_samples"] == len(tasks)
    assert detail["classify_median_ms"] >= 0
    assert detail["route_median_ms"] >= 0
    assert 0 <= result["score"] <= 1
    assert detail["note"] == "smoke perf check on this machine; not a benchmark"


def test_rust_evaluation_comparison_and_artifacts_match_python(tmp_path):
    baseline = {
        "grade_over_100": 80.25,
        "dimensions": {
            "safety": {"score": 1.0},
            "classification": {"score": 0.9},
            "unmeasured": {"score": None},
        },
        "release_gates": {"human_review": True, "context_gate": False},
    }
    current = {
        "grade_over_100": 79.0,
        "dimensions": {
            "safety": {"score": 1.0},
            "classification": {"score": 0.8998},
            "unmeasured": {"score": 0.5},
            "new_dimension": {"score": 1.0},
        },
        "release_gates": {
            "human_review": False,
            "context_gate": True,
            "new_gate": False,
        },
    }
    python_result = evaluate_python_comparison.compare(baseline, current)
    python_dir = tmp_path / "python"
    rust_dir = tmp_path / "rust"
    python_paths = evaluate_python_comparison.write_comparison(python_result, python_dir)
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_compare_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"baseline": baseline, "current": current, "out_dir": str(rust_dir)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    rust_result = json.loads(process.stdout)
    assert rust_result["comparison"] == python_result
    assert rust_result["files"] == [path.name for path in python_paths]
    for name in ("comparison.md", "regressions.csv", "improvements.csv"):
        assert (rust_dir / name).read_bytes() == (python_dir / name).read_bytes()

    no_regression = {"grade_over_100": 80.25, "dimensions": {}, "release_gates": {}}
    python_empty = evaluate_python_comparison.compare(no_regression, no_regression)
    rust_empty_dir = tmp_path / "rust-empty"
    empty_process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_compare_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "baseline": no_regression,
                "current": no_regression,
                "out_dir": str(rust_empty_dir),
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert json.loads(empty_process.stdout)["comparison"] == python_empty
    expected_empty_markdown = (
        b"# Baseline vs current\n\n"
        b"- grade delta: 0.0\n"
        b"- critical regression: NO\n"
        b"- gate regressions: none\n\n"
        b"## Regressions\n\n\n"
        b"## Improvements\n\n"
    )
    assert (rust_empty_dir / "comparison.md").read_bytes() == expected_empty_markdown
