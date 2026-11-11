"""Offline differential contract tests for Rust evaluation metric aggregation."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from agentrouter.evaluation.metrics import classification_metrics
from agentrouter.evaluation.provenance import dataset_quality
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification, Provenance

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
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == dataset_quality(cases)
