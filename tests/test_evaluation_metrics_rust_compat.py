"""Offline differential contract tests for Rust evaluation metric aggregation."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from agentrouter.evaluation.metrics import classification_metrics
from agentrouter.evaluation.provenance import dataset_quality
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
        timeout=120,
        check=False,
    )
    assert rejected.returncode != 0
