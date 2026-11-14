"""End-to-end command compatibility for the Rust human annotation CLI.

All labels made in these tests are synthetic fixtures. The CLI itself never
generates labels; its only labeling path is explicit stdin from a human.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentrouter.annotation import candidates as candidate_mod
from agentrouter.annotation import packs, schema, store
from agentrouter.annotation.adjudicate import Adjudication, resolve
from agentrouter.annotation.compare import compare_all
from agentrouter.annotation.splits import partition

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def rust_evaluate_binary():
    built = subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "-p",
            "agentrouter-evaluation",
            "--bin",
            "agentrouter-evaluate",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
    executable = target / "debug" / "agentrouter-evaluate"
    if os.name == "nt":
        executable = executable.with_suffix(".exe")
    assert executable.exists()
    return executable


def _run(binary, *args: str, input_text: str | None = None):
    return subprocess.run(
        [str(binary), "dataset", *map(str, args)],
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


def _dump(items):
    return [item.model_dump(mode="json", exclude_none=True) for item in items]


def _write_labels(path: Path, items):
    store.save_labels(path, items)


def _label(item, annotator: str, band: str, confidence: float = 0.8):
    return schema.ItemLabels(
        candidate_id=item.id,
        prompt=item.prompt,
        category=item.category,
        labels=[
            schema.AnnotatorLabel(
                annotator=annotator,
                band=schema.ContextBand(band),
                abstain=False,
                rationale=f"{annotator} synthetic test fixture",
                confidence=confidence,
                at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ],
    )


def test_candidate_generation_pack_progress_and_adjudication_pack(tmp_path, rust_evaluate_binary):
    help_result = _run(rust_evaluate_binary, "--help")
    assert help_result.returncode == 0
    assert "adjudication-pack" in help_result.stdout
    annotate_help = _run(rust_evaluate_binary, "annotate", "--help")
    assert annotate_help.returncode == 0
    assert "EOF pauses" in annotate_help.stdout

    pool_path = tmp_path / "pool.yaml"
    generated = _run(
        rust_evaluate_binary,
        "gen-candidates",
        "--out",
        pool_path,
        "--count",
        "20",
        "--seed",
        "-83",
    )
    assert generated.returncode == 0, generated.stderr
    pool = store.load_candidates(pool_path)
    assert _dump(pool) == _dump(candidate_mod.generate(20, seed=-83))
    assert all(not item.notes for item in pool)

    pack_path = tmp_path / "pack.yaml"
    packed = _run(
        rust_evaluate_binary,
        "pack",
        "--annotator",
        "ann_a",
        "--seed",
        "-13",
        "--candidates",
        pool_path,
        "--out",
        pack_path,
    )
    assert packed.returncode == 0, packed.stderr
    pack = store.load_candidates(pack_path)
    assert _dump(pack) == _dump(packs.build_pack(pool, seed=-13))
    assert all(item.template is None and item.notes is None for item in pack)

    one_label = [_label(pack[0], "ann_a", "small")]
    labels_a = tmp_path / "labels_a.jsonl"
    labels_b = tmp_path / "labels_b.jsonl"
    _write_labels(labels_a, one_label)
    _write_labels(labels_b, [_label(pack[0], "ann_b", "large")])
    progress = _run(
        rust_evaluate_binary,
        "progress",
        pack_path,
        "--labels",
        labels_a,
    )
    assert progress.returncode == 0, progress.stderr
    assert progress.stdout.strip() == f"1/{len(pack)} labelled, {len(pack) - 1} remaining."

    adjudication_path = tmp_path / "adjudication.yaml"
    adjudication = _run(
        rust_evaluate_binary,
        "adjudication-pack",
        "--labels",
        labels_a,
        "--labels",
        labels_b,
        "--out",
        adjudication_path,
    )
    assert adjudication.returncode == 0, adjudication.stderr
    disputed = store.load_candidates(adjudication_path)
    expected = packs.adjudication_candidates(one_label, [_label(pack[0], "ann_b", "large")])
    assert _dump(disputed) == _dump(expected)
    assert len(disputed) == 1 and disputed[0].source == "curated"


def test_interactive_annotation_resumes_and_exports_human_input(tmp_path, rust_evaluate_binary):
    pool_path = tmp_path / "pool.yaml"
    generated = _run(rust_evaluate_binary, "gen-candidates", "--out", pool_path, "--count", "10")
    assert generated.returncode == 0, generated.stderr
    pool = store.load_candidates(pool_path)
    labels_path = tmp_path / "human.jsonl"

    first = _run(
        rust_evaluate_binary,
        "annotate",
        pool_path,
        "--annotator",
        "human_one",
        "--out",
        labels_path,
        input_text="a\nuncertain from prompt\n0.4\n",
    )
    assert first.returncode == 0, first.stderr
    assert "Paused." in first.stdout
    labels = store.load_labels(labels_path)
    assert len(labels) == 1 and labels[0].labels[0].abstain

    remaining_answers = "".join("m\nexplicit user input\n0.85\n" for _ in pool[1:])
    resumed = _run(
        rust_evaluate_binary,
        "annotate",
        pool_path,
        "--annotator",
        "human_one",
        "--out",
        labels_path,
        input_text=remaining_answers,
    )
    assert resumed.returncode == 0, resumed.stderr
    labels = store.load_labels(labels_path)
    assert len(labels) == len(pool)
    assert labels[0].labels[0].abstain
    assert all(row.labels[0].annotator == "human_one" for row in labels)

    csv_path = tmp_path / "human.csv"
    exported = _run(rust_evaluate_binary, "export", labels_path, "--csv", csv_path)
    assert exported.returncode == 0, exported.stderr
    assert csv_path.read_bytes().decode("utf-8") == packs.labels_to_csv(labels)


def test_build_adjudication_comparison_and_leakage_pipeline(tmp_path, rust_evaluate_binary):
    pool = candidate_mod.generate(40, seed=905)
    label_a, label_b = [], []
    scope_band = {"small": "small", "existing": "medium", "large": "large"}
    for index, candidate in enumerate(pool):
        band = scope_band[candidate.template.split("/")[1]]
        left = _label(candidate, "ann_a", band)
        right = _label(
            candidate, "ann_b", ("small" if band == "large" else "large") if index == 0 else band
        )
        label_a.append(left)
        label_b.append(right)

    a_path, b_path = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_labels(a_path, label_a)
    _write_labels(b_path, label_b)
    adjudication_path = tmp_path / "adjudications.json"
    adjudication_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": pool[0].id,
                    "adjudicator": "human_adjudicator",
                    "band": label_a[0].labels[0].band.value,
                    "abstain": False,
                    "rationale": "explicit test fixture decision",
                    "confidence": 0.9,
                }
            ]
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "rust-built"
    built = _run(
        rust_evaluate_binary,
        "build",
        "--labels",
        a_path,
        "--labels",
        b_path,
        "--out-dir",
        out_dir,
        "--version",
        "vtest",
        "--adjudications",
        adjudication_path,
    )
    assert built.returncode == 0, built.stderr
    manifest = store.load_manifest(out_dir / "manifest_vtest.json")
    assert sum(manifest.split_counts.values()) == len(pool)
    assert manifest.frozen_holdout_untouched
    assert manifest.split_sha256
    leakage_report = json.loads((out_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert leakage_report["dev_leaks"] == leakage_report["holdout_leaks"] == 0

    frozen_path = ROOT / "agentrouter/benchmarks/context_band_holdout_v1.yaml"
    import yaml

    frozen = [
        row["prompt"] for row in yaml.safe_load(frozen_path.read_text(encoding="utf-8"))["cases"]
    ]
    merged = packs.merge_by_candidate(label_a, label_b)
    resolved = []
    decision = Adjudication(
        adjudicator="human_adjudicator",
        band=label_a[0].labels[0].band,
        abstain=False,
        rationale="explicit test fixture decision",
        confidence=0.9,
    )
    for item in merged.values():
        resolved.append(
            resolve(item, adjudication=decision if item.candidate_id == pool[0].id else None)
        )
    expected_splits = partition(
        [item for item in resolved if item is not None], frozen_holdout_prompts=frozen
    )
    for split, expected_items in expected_splits.as_dict().items():
        actual_items = store.load_dataset(out_dir / f"context_band_{split}_vtest.yaml")
        assert _dump(actual_items) == _dump(expected_items)

    dev_path = out_dir / "context_band_dev_vtest.yaml"
    compare_path = tmp_path / "comparison.json"
    compared = _run(rust_evaluate_binary, "compare", dev_path, "--out", compare_path)
    assert compared.returncode == 0, compared.stderr
    expected_compare = {
        name: report.__dict__ for name, report in compare_all(expected_splits.dev).items()
    }
    actual_compare = json.loads(compare_path.read_text(encoding="utf-8"))
    expected_compare = json.loads(json.dumps(expected_compare))
    assert actual_compare == expected_compare

    check = _run(rust_evaluate_binary, "leakage", out_dir / "context_band_holdout_vtest.yaml")
    assert check.returncode == 0, check.stderr
    assert "0 leak(s)" in check.stdout


def test_build_refuses_unresolved_disagreement(tmp_path, rust_evaluate_binary):
    candidate = candidate_mod.generate(10, seed=117)[0]
    first, second = [_label(candidate, "ann_a", "small")], [_label(candidate, "ann_b", "large")]
    a_path, b_path = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_labels(a_path, first)
    _write_labels(b_path, second)
    out_dir = tmp_path / "must-not-build"
    result = _run(
        rust_evaluate_binary,
        "build",
        "--labels",
        a_path,
        "--labels",
        b_path,
        "--out-dir",
        out_dir,
    )
    assert result.returncode == 2
    assert "need adjudication" in result.stderr
    assert not out_dir.exists()
