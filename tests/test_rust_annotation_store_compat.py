"""File and hash contract checks for the Rust annotation artifact store."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.schema import AdjudicatedItem, Candidate, DatasetManifest, ItemLabels
from agentrouter.annotation.store import (
    load_candidates,
    load_dataset,
    load_labels,
    load_manifest,
    save_candidates,
    save_dataset,
    save_labels,
    save_manifest,
    split_sha256,
)

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(operation: str, path: Path, **kwargs):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_store_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"operation": operation, "path": str(path), **kwargs}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _dump(values):
    return [value.model_dump(mode="json") for value in values]


def _items():
    return [
        AdjudicatedItem(
            id="z-last",
            prompt="résumé the API 🧭",
            category="review",
            band="medium",
            label_source="curated",
            annotators=["reviewer-a"],
            rationale="Unicode evidence",
            confidence=0.8125,
            split="dev",
        ),
        AdjudicatedItem(
            id="a-first",
            prompt="small helper",
            category="coding",
            band="small",
            label_source="generated_candidate",
            rationale="brief",
            confidence=1.0,
        ),
    ]


def test_rust_split_hash_matches_python_for_order_and_unicode():
    items = _items()
    process = _rust("split_sha256", Path("unused.json"), items=_dump(items))
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["sha256"] == split_sha256(items)


def test_rust_candidate_yaml_round_trip_both_directions(tmp_path):
    candidates = [
        Candidate(
            id="c1",
            prompt="Café, review the parser",
            category="review",
            template="review/large",
        ),
        Candidate(id="c2", prompt="small fix", category="coding", notes="private notes"),
    ]
    rust_path = tmp_path / "nested" / "candidates.yaml"
    process = _rust("save_candidates", rust_path, candidates=_dump(candidates))
    assert process.returncode == 0, process.stderr
    assert load_candidates(rust_path) == candidates

    python_path = tmp_path / "python-candidates.yaml"
    save_candidates(python_path, candidates)
    process = _rust("load_candidates", python_path)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == _dump(candidates)


def test_rust_annotation_jsonl_round_trip_and_exact_encoding(tmp_path):
    labels = [
        ItemLabels(
            candidate_id="c1",
            prompt="café",
            category="review",
            labels=[],
        )
    ]
    rust_path = tmp_path / "labels.jsonl"
    process = _rust("save_labels", rust_path, labels=_dump(labels))
    assert process.returncode == 0, process.stderr
    python_path = tmp_path / "python-labels.jsonl"
    save_labels(python_path, labels)
    assert rust_path.read_bytes() == python_path.read_bytes()

    with rust_path.open("a", encoding="utf-8") as stream:
        stream.write("  \n")
    process = _rust("load_labels", rust_path)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == _dump(labels)
    assert load_labels(rust_path) == labels


def test_rust_dataset_yaml_sorting_manifest_json_and_loaders(tmp_path):
    items = _items()
    rust_dataset = tmp_path / "dataset.yaml"
    process = _rust("save_dataset", rust_dataset, items=_dump(items))
    assert process.returncode == 0, process.stderr
    loaded = load_dataset(rust_dataset)
    assert [item.id for item in loaded] == ["a-first", "z-last"]
    assert loaded == sorted(items, key=lambda item: item.id)

    python_dataset = tmp_path / "python-dataset.yaml"
    save_dataset(python_dataset, items)
    process = _rust("load_dataset", python_dataset)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == _dump(sorted(items, key=lambda item: item.id))

    manifest = DatasetManifest(
        schema_version=10**79 + 123456789,
        version="v2.0.1",
        created="2026-11-11",
        split_counts={"dev": 2, "train": 8, "holdout": 10**79 + 123456789},
        category_counts={"review": 10**79 + 123456789},
        band_counts={"large": 10**79 + 123456789},
        provenance="human review — frozen holdout untouched",
    )
    rust_manifest = tmp_path / "manifest.json"
    process = _rust("save_manifest", rust_manifest, manifest=manifest.model_dump(mode="json"))
    assert process.returncode == 0, process.stderr
    python_manifest = tmp_path / "python-manifest.json"
    save_manifest(python_manifest, manifest)
    assert rust_manifest.read_bytes() == python_manifest.read_bytes()
    process = _rust("load_manifest", python_manifest)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == manifest.model_dump(mode="json")
    assert load_manifest(rust_manifest) == manifest
