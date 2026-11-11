"""Python/Rust differentials for deterministic annotation pack operations."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.packs import (
    adjudication_candidates,
    build_pack,
    disagreement_items,
    labels_to_csv,
    merge_by_candidate,
    pending,
    progress,
)
from agentrouter.annotation.schema import AnnotatorLabel, Candidate, ItemLabels

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(operation: str, **kwargs):
    request = {"operation": operation, **kwargs}
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_packs_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _dump(values):
    return [value.model_dump(mode="json") for value in values]


@pytest.mark.parametrize("seed", [0, 1, 20260731, -17, 2**40 + 3, 2**80 + 17])
def test_rust_blinded_pack_order_matches_python(seed):
    candidates = [
        Candidate(
            id=f"cand-{i}",
            prompt=f"prompt number {i}",
            category="coding",
            source="curated",
            template="coding/large",
            notes="private provenance",
        )
        for i in range(19)
    ]
    expected = _dump(build_pack(candidates, seed=seed))
    process = _rust("build_pack", candidates=_dump(candidates), seed=str(seed))
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


def test_rust_pending_and_label_free_progress_match_python():
    candidates = [Candidate(id=f"c{i}", prompt=f"prompt {i}", category="review") for i in range(5)]
    done = [
        ItemLabels(candidate_id="c1", prompt="prompt 1", category="review"),
        ItemLabels(candidate_id="outside", prompt="other", category="review"),
        ItemLabels(candidate_id="c1", prompt="duplicate", category="review"),
    ]
    process = _rust("pending", candidates=_dump(candidates), done=_dump(done))
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == _dump(pending(candidates, done))
    process = _rust("progress", candidates=_dump(candidates), done=_dump(done))
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == progress(candidates, done)


def test_rust_merge_disagreement_adjudication_pack_and_csv_match_python():
    def item(candidate_id, annotator, band):
        return ItemLabels(
            candidate_id=candidate_id,
            prompt=f"prompt,{candidate_id}",
            category="review",
            labels=[
                AnnotatorLabel(
                    annotator=annotator,
                    band=band,
                    rationale='said "review"',
                    confidence=0.5,
                )
            ],
        )

    first = [
        item("c1", "reviewer-a", "small"),
        item("c2", "reviewer-a", "large"),
        item("c3", "reviewer-a", "medium"),
    ]
    second = [item("c1", "reviewer-b", "small"), item("c2", "reviewer-b", "small")]
    first[0].labels[0].confidence = 1.0
    first[1].labels[0].confidence = 0.000001
    label_sets = [_dump(first), _dump(second)]
    merged = list(merge_by_candidate(first, second).values())
    for operation, expected in [
        ("merge", _dump(merged)),
        ("disagreements", _dump(disagreement_items(first, second))),
        ("adjudication_candidates", _dump(adjudication_candidates(first, second))),
    ]:
        process = _rust(operation, label_sets=label_sets)
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout) == expected
    process = _rust("csv", done=_dump(merged))
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == labels_to_csv(merged)
