"""CLI tests for `agentrouter dataset ...` (TASK-011).

Exercises the full offline pipeline through the Typer app: generate candidates,
collect two annotators' labels, build leakage-safe splits with a manifest,
compare strategies, and run the frozen-holdout leakage check. The interactive
annotate loop is covered with injected stdin.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from agentrouter.annotation import store
from agentrouter.cli import app

runner = CliRunner()


def _label_row(
    cid: str, prompt: str, category: str, annotator: str, band: str, conf: float
) -> dict:
    return {
        "candidate_id": cid,
        "prompt": prompt,
        "category": category,
        "labels": [
            {
                "annotator": annotator,
                "band": band,
                "abstain": False,
                "rationale": f"{annotator} scope call",
                "confidence": conf,
            }
        ],
    }


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def test_gen_candidates_writes_unlabelled_pool(tmp_path):
    out = tmp_path / "pool.yaml"
    r = runner.invoke(app, ["dataset", "gen-candidates", "--out", str(out), "--count", "30"])
    assert r.exit_code == 0, r.output
    pool = store.load_candidates(out)
    assert 10 <= len(pool) <= 30
    assert all(c.source == "generated_candidate" for c in pool)


def test_build_compare_and_leakage_pipeline(tmp_path):
    # 1. generate a small candidate pool
    pool_path = tmp_path / "pool.yaml"
    runner.invoke(app, ["dataset", "gen-candidates", "--out", str(pool_path), "--count", "30"])
    pool = store.load_candidates(pool_path)

    # 2. two annotators agree using the scope hint in each candidate's template
    scope_band = {"small": "small", "existing": "medium", "large": "large"}
    a_rows, b_rows = [], []
    for c in pool:
        band = scope_band[c.template.split("/")[1]]
        a_rows.append(_label_row(c.id, c.prompt, c.category, "ann_a", band, 0.85))
        b_rows.append(_label_row(c.id, c.prompt, c.category, "ann_b", band, 0.75))
    a_path, b_path = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_jsonl(a_path, a_rows)
    _write_jsonl(b_path, b_rows)

    # 3. build leakage-safe splits + manifest
    out_dir = tmp_path / "built"
    r = runner.invoke(
        app,
        [
            "dataset",
            "build",
            "--labels",
            str(a_path),
            "--labels",
            str(b_path),
            "--out-dir",
            str(out_dir),
            "--version",
            "vtest",
        ],
    )
    assert r.exit_code == 0, r.output
    manifest = store.load_manifest(out_dir / "manifest_vtest.json")
    assert manifest.frozen_holdout_untouched is True
    assert sum(manifest.split_counts.values()) == len(pool)
    assert manifest.split_sha256  # every split hashed
    leak = json.loads((out_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert leak["dev_leaks"] == 0 and leak["holdout_leaks"] == 0

    # 4. compare on the built dev split
    dev = out_dir / "context_band_dev_vtest.yaml"
    rep = tmp_path / "cmp.json"
    r = runner.invoke(app, ["dataset", "compare", str(dev), "--out", str(rep)])
    assert r.exit_code == 0, r.output
    payload = json.loads(rep.read_text(encoding="utf-8"))
    assert set(payload) == {"rules", "learned", "hybrid"}

    # 5. leakage check of the built holdout vs the frozen holdout -> clean
    holdout = out_dir / "context_band_holdout_vtest.yaml"
    r = runner.invoke(app, ["dataset", "leakage", str(holdout)])
    assert r.exit_code == 0, r.output  # exit 0 == no leaks


def test_build_blocks_on_unresolved_disagreement(tmp_path):
    pool_path = tmp_path / "pool.yaml"
    runner.invoke(app, ["dataset", "gen-candidates", "--out", str(pool_path), "--count", "12"])
    pool = store.load_candidates(pool_path)
    a_rows = [_label_row(c.id, c.prompt, c.category, "ann_a", "small", 0.8) for c in pool]
    b_rows = [
        _label_row(c.id, c.prompt, c.category, "ann_b", "large", 0.8) for c in pool
    ]  # disagree
    a_path, b_path = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_jsonl(a_path, a_rows)
    _write_jsonl(b_path, b_rows)
    r = runner.invoke(
        app,
        [
            "dataset",
            "build",
            "--labels",
            str(a_path),
            "--labels",
            str(b_path),
            "--out-dir",
            str(tmp_path / "out"),
            "--version",
            "vx",
        ],
    )
    assert r.exit_code == 2  # refuses to build until disagreements are adjudicated
    assert "adjudication" in r.output.lower()


def test_interactive_annotate_records_band_and_abstain(tmp_path):
    pool_path = tmp_path / "pool.yaml"
    runner.invoke(app, ["dataset", "gen-candidates", "--out", str(pool_path), "--count", "12"])
    pool = store.load_candidates(pool_path)
    out = tmp_path / "labels.jsonl"
    # answer first item as small, abstain on the second, then Ctrl-C-equivalent EOF
    stdin = "s\nlooks self-contained\n0.9\na\ncannot tell\n0.3\n" + "s\nx\n0.5\n" * len(pool)
    r = runner.invoke(
        app,
        ["dataset", "annotate", str(pool_path), "--annotator", "ann_a", "--out", str(out)],
        input=stdin,
    )
    assert r.exit_code == 0, r.output
    labels = store.load_labels(out)
    assert labels[0].labels[0].band is not None
    assert labels[1].labels[0].abstain is True
