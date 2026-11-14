"""Differential checks for deterministic annotation data splits."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.schema import AdjudicatedItem
from agentrouter.annotation.splits import LeakageError, partition

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _item(identifier: str, prompt: str) -> AdjudicatedItem:
    return AdjudicatedItem(
        id=identifier,
        prompt=prompt,
        category="review",
        band="medium",
        label_source="curated",
        annotators=["annotator-a", "annotator-b"],
        rationale="Human reviewed this prompt.",
        confidence=0.8,
        review_status="approved",
    )


def _rust(items, frozen_holdout_prompts=(), ratios=None):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_splits_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "items": [item.model_dump(mode="json") for item in items],
                "frozen_holdout_prompts": list(frozen_holdout_prompts),
                "ratios": ratios,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    "ratios",
    [None, {"train": 0.5, "dev": 0.3, "holdout": 0.2}],
)
def test_rust_annotation_partition_matches_python(ratios):
    items = [
        _item("one", "Review the payment API for security issues"),
        _item("two", "Review the payment API for security issue!"),
        _item("three", "Write a concise release note for the last change"),
        _item("four", "Compare two database indexing strategies"),
        _item("five", "Explain how the background worker retries failures"),
        _item("six", "Check whether the cache invalidation policy is safe"),
    ]
    expected = partition(items, ratios=ratios)
    process = _rust(items, ratios=ratios)
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    assert actual == {
        split: [item.model_dump(mode="json") for item in values]
        for split, values in expected.as_dict().items()
    }


def test_rust_annotation_partition_refuses_frozen_holdout_leakage():
    items = [_item("one", "This exact prompt is already in frozen holdout")]
    frozen = ["This exact prompt is already in frozen holdout"]
    ratios = {"train": 0.0, "dev": 1.0, "holdout": 0.0}
    with pytest.raises(LeakageError) as error:
        partition(items, frozen_holdout_prompts=frozen, ratios=ratios)
    process = _rust(items, frozen, ratios)
    assert process.returncode == 3
    assert process.stderr.strip() == str(error.value)
