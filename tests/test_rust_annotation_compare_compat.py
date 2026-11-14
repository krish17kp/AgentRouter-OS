"""Differential tests for rules/learned/hybrid context-band comparison."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.compare import compare_all
from agentrouter.annotation.schema import AdjudicatedItem

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _item(identifier: str, prompt: str, band: str | None, *, abstained: bool = False):
    return AdjudicatedItem(
        id=identifier,
        prompt=prompt,
        category="analysis",
        band=band,
        abstained=abstained,
        label_source="curated",
        rationale="independent comparison fixture",
        confidence=0.8,
        split="dev",
    )


def test_rust_annotation_compare_matches_python_reports():
    items = [
        _item("1", "Write a haiku about rain", "small"),
        _item("2", "Review this complete Python repository for security issues", "large"),
        _item("3", "Summarize these 12000 tokens of legal documents", "large"),
        _item("4", "Explain a simple arithmetic expression", "small"),
        _item("5", "Audit the existing payments service across 250 files", "medium"),
        _item("6", "unlabelled item", None, abstained=True),
    ]
    expected = json.loads(
        json.dumps({strategy: report.__dict__ for strategy, report in compare_all(items).items()})
    )
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_compare_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"items": [item.model_dump(mode="json") for item in items]}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize("threshold", [0.0, 0.45, 0.6, 1.0])
def test_rust_hybrid_threshold_matches_python(threshold):
    items = [
        _item("1", "Write a haiku about rain", "small"),
        _item("2", "Review this complete Python repository for security issues", "large"),
        _item("3", "Explain a simple arithmetic expression", "small"),
    ]
    expected = json.loads(
        json.dumps(
            {
                strategy: report.__dict__
                for strategy, report in compare_all(items, threshold=threshold).items()
            }
        )
    )
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_compare_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {"items": [item.model_dump(mode="json") for item in items], "threshold": threshold}
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    actual = json.loads(process.stdout)
    assert actual == expected
