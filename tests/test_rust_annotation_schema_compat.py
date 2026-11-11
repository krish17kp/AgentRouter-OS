"""Differential checks for annotation artifact schemas and defaults."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentrouter.annotation.schema import (
    AdjudicatedItem,
    AnnotatorLabel,
    Candidate,
    DatasetManifest,
    ItemLabels,
)

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(model, value):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_schema_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"model": model, "value": value}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def test_rust_annotation_artifact_schemas_match_python():
    label_a = AnnotatorLabel(
        annotator="reviewer-a", band="medium", rationale="existing context", confidence=0.8
    )
    label_b = AnnotatorLabel(
        annotator="reviewer-b", band="medium", rationale="repository scope", confidence=0.9
    )
    models = [
        ("candidate", Candidate(id="candidate-1", prompt="Review this service", category="review")),
        ("annotator_label", label_a),
        (
            "item_labels",
            ItemLabels(
                candidate_id="candidate-1",
                prompt="Review this service",
                category="review",
                labels=[label_a, label_b],
            ),
        ),
        (
            "adjudicated_item",
            AdjudicatedItem(
                id="candidate-1",
                prompt="Review this service",
                category="review",
                band="medium",
                label_source="curated",
                annotators=["reviewer-a", "reviewer-b"],
                rationale="Independent agreement.",
                confidence=0.85,
            ),
        ),
        (
            "dataset_manifest",
            DatasetManifest(version="v2.0", created="2026-11-11T00:00:00Z"),
        ),
    ]
    for model, value in models:
        expected_value = value.model_dump(mode="json")
        process = _rust(model, expected_value)
        assert process.returncode == 0, process.stderr
        actual = json.loads(process.stdout)
        expected = {"value": expected_value}
        if isinstance(value, ItemLabels):
            expected.update({"annotators": value.annotators, "agrees": value.agrees})
        assert actual == expected


@pytest.mark.parametrize(
    ("model", "value"),
    [
        (
            "candidate",
            {
                "id": "bad",
                "prompt": "bad",
                "category": "not-a-category",
                "source": "generated_candidate",
                "template": None,
                "notes": None,
            },
        ),
        (
            "annotator_label",
            {
                "annotator": "reviewer-a",
                "band": "medium",
                "abstain": True,
                "rationale": "conflicting schema",
                "confidence": 0.7,
                "at": None,
            },
        ),
        (
            "adjudicated_item",
            {
                "id": "bad",
                "prompt": "bad",
                "category": "review",
                "band": None,
                "abstained": False,
                "label_source": "curated",
                "annotators": [],
                "adjudicated_by": None,
                "rationale": "missing band",
                "confidence": 0.5,
                "split": None,
                "review_status": "pending_human_review",
            },
        ),
    ],
)
def test_rust_annotation_schema_rejects_invalid_models(model, value):
    process = _rust(model, value)
    assert process.returncode != 0
    with pytest.raises(ValidationError):
        if model == "candidate":
            Candidate.model_validate(value)
        elif model == "annotator_label":
            AnnotatorLabel.model_validate(value)
        else:
            AdjudicatedItem.model_validate(value)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-11-11T12:30:00Z",
        "2026-11-11T12:30:00+05:30",
        "2026-11-11 12:30:00.120000",
        "2026-11-11",
        "2026-11-11T12:30:00.123456789Z",
        "2026-11-11T12:30",
        "2026-11-11T12:30:00,25+05:30",
        0,
        1.5,
        "0",
        None,
    ],
)
def test_rust_annotation_datetime_matches_python_parse_and_serialization(timestamp):
    value = AnnotatorLabel(
        annotator="reviewer-a",
        band="medium",
        rationale="timestamp fixture",
        confidence=0.75,
        at=timestamp,
    )
    expected = value.model_dump(mode="json")
    process = _rust("annotator_label", expected)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"value": expected}


def test_rust_annotation_datetime_rejects_invalid_value_like_python():
    invalid = {
        "annotator": "reviewer-a",
        "band": "medium",
        "abstain": False,
        "rationale": "invalid timestamp fixture",
        "confidence": 0.75,
        "at": "not-a-date",
    }
    process = _rust("annotator_label", invalid)
    assert process.returncode != 0
    with pytest.raises(ValidationError):
        AnnotatorLabel.model_validate(invalid)


@pytest.mark.parametrize("confidence", ["0.75", True])
def test_rust_annotation_confidence_matches_pydantic_scalar_coercion(confidence):
    value = {
        "annotator": "reviewer-a",
        "band": "medium",
        "abstain": False,
        "rationale": "coercion fixture",
        "confidence": confidence,
        "at": None,
    }
    expected = AnnotatorLabel.model_validate(value).model_dump(mode="json")
    process = _rust("annotator_label", value)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"value": expected}
