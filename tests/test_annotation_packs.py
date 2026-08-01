"""Tests for blinded annotation-pack operations + CLI (TASK-012).

Covers: independent per-annotator ordering over the same candidate set, resume
(pending), label-free progress, disagreements-only adjudication packs that never
auto-resolve or reveal bands, CSV export, and the corresponding CLI commands.
"""

from __future__ import annotations

import csv
import io

from typer.testing import CliRunner

from agentrouter.annotation import candidates, packs, store
from agentrouter.annotation.schema import AnnotatorLabel, ItemLabels
from agentrouter.cli import app
from agentrouter.schema import ContextBand

runner = CliRunner()


def _il(cid, band, annotator, *, abstain=False, prompt="p", category="coding"):
    return ItemLabels(
        candidate_id=cid,
        prompt=prompt,
        category=category,
        labels=[
            AnnotatorLabel(
                annotator=annotator, band=band, abstain=abstain, rationale="r", confidence=0.8
            )
        ],
    )


# --- pack ordering ----------------------------------------------------------


def test_packs_are_independently_ordered_over_the_same_set():
    pool = candidates.generate()
    a = packs.build_pack(pool, seed=1)
    b = packs.build_pack(pool, seed=2)
    assert [c.id for c in a] != [c.id for c in b]  # independent order
    assert {c.id for c in a} == {c.id for c in b} == {c.id for c in pool}  # same set
    assert [c.id for c in a] == [c.id for c in packs.build_pack(pool, seed=1)]  # deterministic


def test_pack_contains_no_labels_or_predictions():
    pool = candidates.generate()
    a = packs.build_pack(pool, seed=7)
    # Candidate schema has no band/prediction field — structural blinding.
    assert all(not hasattr(c, "band") for c in a)
    assert all(c.source in ("generated_candidate", "curated", "real_prompt") for c in a)


# --- resume / progress ------------------------------------------------------


def test_pending_and_progress_are_label_free():
    pool = candidates.generate()[:10]
    done = [_il(pool[0].id, ContextBand.small, "A"), _il(pool[1].id, ContextBand.large, "A")]
    assert len(packs.pending(pool, done)) == 8
    prog = packs.progress(pool, done)
    assert prog == {"total": 10, "done": 2, "remaining": 8}  # counts only, no bands


# --- adjudication -----------------------------------------------------------


def test_disagreement_items_only_surfaces_conflicts():
    a = [_il("agree", ContextBand.small, "A"), _il("conflict", ContextBand.small, "A")]
    b = [_il("agree", ContextBand.small, "B"), _il("conflict", ContextBand.large, "B")]
    disputed = {i.candidate_id for i in packs.disagreement_items(a, b)}
    assert disputed == {"conflict"}  # agreement excluded


def test_single_annotator_item_is_surfaced_for_the_second_label():
    a = [_il("only_a", ContextBand.small, "A")]
    disputed = {i.candidate_id for i in packs.disagreement_items(a, [])}
    assert disputed == {"only_a"}  # needs the second annotator, not silently accepted


def test_adjudication_pack_is_blinded():
    a = [_il("c", ContextBand.small, "A", prompt="do X")]
    b = [_il("c", ContextBand.large, "B", prompt="do X")]
    pack = packs.adjudication_candidates(a, b)
    assert [c.id for c in pack] == ["c"]
    assert all(not hasattr(c, "band") for c in pack)  # adjudicator sees no prior bands


# --- csv export -------------------------------------------------------------


def test_labels_to_csv_flattens_every_label():
    labels = [
        _il("c1", ContextBand.small, "A"),
        _il("c2", None, "B", abstain=True),
    ]
    rows = list(csv.reader(io.StringIO(packs.labels_to_csv(labels))))
    assert rows[0][0] == "candidate_id"
    assert len(rows) == 3  # header + 2 labels
    abstain_row = next(r for r in rows[1:] if r[0] == "c2")
    assert abstain_row[4] == "" and abstain_row[5] == "True"  # empty band, abstain flagged


# --- CLI --------------------------------------------------------------------


def test_cli_pack_annotate_resume_progress_export(tmp_path):
    # blinded pack for annotator A
    packA = tmp_path / "packA.yaml"
    r = runner.invoke(
        app, ["dataset", "pack", "--annotator", "A", "--seed", "3", "--out", str(packA)]
    )
    assert r.exit_code == 0, r.output
    pool = store.load_candidates(packA)

    out = tmp_path / "A.jsonl"
    # label only the first two, then "pause" (EOF)
    stdin = "s\nself-contained\n0.9\nl\nbig corpus\n0.6\n"
    r = runner.invoke(
        app, ["dataset", "annotate", str(packA), "--annotator", "A", "--out", str(out)], input=stdin
    )
    assert r.exit_code == 0, r.output
    assert len(store.load_labels(out)) == 2

    # progress is label-free
    r = runner.invoke(app, ["dataset", "progress", str(packA), "--labels", str(out)])
    assert r.exit_code == 0 and f"2/{len(pool)}" in r.output

    # resume: previously-labelled ids are skipped; label one more
    r = runner.invoke(
        app,
        ["dataset", "annotate", str(packA), "--annotator", "A", "--out", str(out)],
        input="m\nexisting component\n0.7\n",
    )
    assert r.exit_code == 0, r.output
    assert len(store.load_labels(out)) == 3  # appended, not overwritten

    # CSV export
    csv_out = tmp_path / "A.csv"
    r = runner.invoke(app, ["dataset", "export", str(out), "--csv", str(csv_out)])
    assert r.exit_code == 0, r.output
    assert "candidate_id" in csv_out.read_text(encoding="utf-8")


def test_cli_adjudication_pack_only_disagreements(tmp_path):
    def _write(path, rows):
        path.write_text(
            "".join(
                __import__("json").dumps(r.model_dump(mode="json"), sort_keys=True) + "\n"
                for r in rows
            ),
            encoding="utf-8",
        )

    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, [_il("agree", ContextBand.small, "A"), _il("conflict", ContextBand.small, "A")])
    _write(b, [_il("agree", ContextBand.small, "B"), _il("conflict", ContextBand.large, "B")])
    out = tmp_path / "adj.yaml"
    r = runner.invoke(
        app,
        ["dataset", "adjudication-pack", "--labels", str(a), "--labels", str(b), "--out", str(out)],
    )
    assert r.exit_code == 0, r.output
    disputed = [c.id for c in store.load_candidates(out)]
    assert disputed == ["conflict"]  # agreement excluded; no auto-adjudication
