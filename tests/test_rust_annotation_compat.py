"""Differential checks for human-only annotation resolution in Rust."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from agentrouter.annotation.adjudicate import Adjudication, needs_adjudication, resolve
from agentrouter.annotation.schema import AnnotatorLabel, ItemLabels

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("labels", "decision", "label_source"),
    [
        (
            [
                AnnotatorLabel(annotator="a", band="medium", rationale="a", confidence=0.7),
                AnnotatorLabel(annotator="b", band="medium", rationale="b", confidence=0.8),
            ],
            None,
            "curated",
        ),
        (
            [
                AnnotatorLabel(annotator="a", abstain=True, rationale="unsure", confidence=0.3),
                AnnotatorLabel(annotator="b", abstain=True, rationale="unclear", confidence=0.4),
            ],
            None,
            "generated_candidate",
        ),
        (
            [
                AnnotatorLabel(annotator="a", band="small", rationale="short", confidence=0.9),
                AnnotatorLabel(annotator="b", band="large", rationale="long", confidence=0.8),
            ],
            None,
            "real_prompt",
        ),
        (
            [
                AnnotatorLabel(annotator="a", band="small", rationale="short", confidence=0.9),
                AnnotatorLabel(annotator="b", band="large", rationale="long", confidence=0.8),
            ],
            Adjudication(
                adjudicator="reviewer-c",
                band="large",
                abstain=False,
                rationale="The prompt contains a full repository.",
                confidence=0.77777,
            ),
            "curated",
        ),
        (
            [
                AnnotatorLabel(annotator="a", band="medium", rationale="context", confidence=0.7),
                AnnotatorLabel(annotator="b", abstain=True, rationale="uncertain", confidence=0.5),
            ],
            Adjudication(
                adjudicator="reviewer-c",
                band="medium",
                abstain=False,
                rationale="Human review resolved the mixed abstention.",
            ),
            "generated_candidate",
        ),
        (
            [
                AnnotatorLabel(annotator="a", band="small", rationale="short", confidence=0.9),
                AnnotatorLabel(annotator="b", band="large", rationale="long", confidence=0.8),
            ],
            Adjudication(
                adjudicator="reviewer-c",
                band=None,
                abstain=True,
                rationale="Evidence is insufficient to select a band.",
            ),
            "curated",
        ),
        ([], None, "generated_candidate"),
    ],
)
def test_rust_annotation_resolution_matches_python(labels, decision, label_source):
    item = ItemLabels(
        candidate_id="case-1",
        prompt="Review this repository for security issues.",
        category="review",
        labels=labels,
    )
    expected = resolve(item, label_source=label_source, adjudication=decision)
    expected_json = expected.model_dump(mode="json") if expected is not None else None
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_adjudicate_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "item": item.model_dump(mode="json"),
                "label_source": label_source,
                "adjudication": asdict(decision) if decision else None,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == {
        "needs_adjudication": needs_adjudication(item),
        "resolved": expected_json,
    }
