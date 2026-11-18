"""Tests for the context-band annotation program (TASK-011).

Covers the data contract, dedup/leakage, candidate generation, adjudication,
leakage-safe splitting, and the rules/learned/hybrid comparison. A dedicated test
proves the shipped candidate pool never leaks the frozen TASK-009 holdout, and
another proves the frozen holdout file itself is untouched (SHA unchanged).
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest
import yaml

from agentrouter.annotation import CATEGORIES, candidates, dedup, graph_signals, store
from agentrouter.annotation.adjudicate import Adjudication, needs_adjudication, resolve
from agentrouter.annotation.compare import compare_all, predict
from agentrouter.annotation.schema import (
    AdjudicatedItem,
    AnnotatorLabel,
    Candidate,
    ItemLabels,
)
from agentrouter.annotation.splits import LeakageError, partition
from agentrouter.evaluation.context_bands import HOLDOUT_FILE, HOLDOUT_SHA256
from agentrouter.schema import ContextBand

_POOL = "agentrouter/benchmarks/context_band/candidates_v1.yaml"


def _frozen_prompts() -> list[str]:
    raw = yaml.safe_load(
        (resources.files("agentrouter.benchmarks") / HOLDOUT_FILE).read_text(encoding="utf-8")
    )
    return [c["prompt"] for c in raw["cases"]]


# --- schema -----------------------------------------------------------------


def test_label_requires_band_xor_abstain():
    with pytest.raises(ValueError):
        AnnotatorLabel(
            annotator="a", abstain=True, band=ContextBand.small, rationale="x", confidence=0.5
        )
    with pytest.raises(ValueError):
        AnnotatorLabel(annotator="a", abstain=False, band=None, rationale="x", confidence=0.5)
    ok = AnnotatorLabel(annotator="a", abstain=True, rationale="cannot infer", confidence=0.4)
    assert ok.band is None


def test_candidate_rejects_unknown_category_and_source():
    with pytest.raises(ValueError):
        Candidate(id="c1", prompt="hi", category="not-a-category")
    with pytest.raises(ValueError):
        Candidate(id="c1", prompt="hi", category="coding", source="scraped")


def test_adjudicated_item_band_xor_abstain():
    with pytest.raises(ValueError):
        AdjudicatedItem(
            id="i",
            prompt="p",
            category="coding",
            abstained=True,
            band=ContextBand.small,
            label_source="generated_candidate",
            rationale="r",
            confidence=0.5,
        )


# --- dedup / leakage --------------------------------------------------------


def test_normalize_and_exact_duplicate():
    assert dedup.normalize("Fix the BUG!!!") == dedup.normalize("fix the bug")
    assert dedup.similarity("fix the bug", "Fix the BUG!") == 1.0


def test_near_duplicate_detected_and_distinct_kept_apart():
    a = "Add graceful shutdown to the running daemon service now"
    b = "Add graceful shutdown to the running daemon service today"
    assert dedup.similarity(a, b) >= dedup.NEAR_THRESHOLD
    assert dedup.similarity(a, "Write a haiku about the sea") < dedup.NEAR_THRESHOLD


def test_cluster_groups_near_duplicates():
    prompts = ["fix the auth bug now", "fix the auth bug today", "write a poem"]
    groups = dedup.cluster(prompts)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_find_leakage_reports_exact_and_near():
    ref = ["Summarize the quarterly report"]
    leaks = dedup.find_leakage(["Summarize the quarterly report"], ref)
    assert leaks and leaks[0].kind == "exact"


# --- candidate generation ---------------------------------------------------


def test_generate_is_deterministic_unique_and_covers_all_categories():
    a = candidates.generate()
    b = candidates.generate()
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]  # deterministic
    prompts = [c.prompt for c in a]
    assert len(prompts) == len(set(prompts))  # no exact repeats
    assert {c.category for c in a} == set(CATEGORIES)  # every category present
    assert all(c.source == "generated_candidate" for c in a)  # never auto-labelled


def test_committed_pool_does_not_leak_frozen_holdout():
    pool = store.load_candidates(Path(_POOL))
    leaks = dedup.find_leakage([c.prompt for c in pool], _frozen_prompts())
    assert leaks == [], f"candidate pool leaks the frozen holdout: {leaks[:3]}"


def test_frozen_holdout_is_untouched():
    # Reuse the production hash (newline-canonicalised) so a Windows CRLF checkout
    # cannot spuriously fail the freeze lock.
    from agentrouter.evaluation.context_bands import _sha256, gold_path

    assert _sha256(gold_path(HOLDOUT_FILE)) == HOLDOUT_SHA256


# --- adjudication -----------------------------------------------------------


def _labels(a: ContextBand | None, b: ContextBand | None, *, a_abstain=False, b_abstain=False):
    return ItemLabels(
        candidate_id="c1",
        prompt="p",
        category="coding",
        labels=[
            AnnotatorLabel(
                annotator="A", band=a, abstain=a_abstain, rationale="ra", confidence=0.8
            ),
            AnnotatorLabel(
                annotator="B", band=b, abstain=b_abstain, rationale="rb", confidence=0.6
            ),
        ],
    )


def test_agreement_resolves_without_adjudicator():
    item = _labels(ContextBand.small, ContextBand.small)
    assert not needs_adjudication(item)
    out = resolve(item)
    assert out.band is ContextBand.small and out.adjudicated_by is None
    assert out.confidence == pytest.approx(0.7)


def test_unanimous_abstention_records_abstained_item():
    item = _labels(None, None, a_abstain=True, b_abstain=True)
    out = resolve(item)
    assert out.abstained is True and out.band is None


def test_disagreement_needs_adjudication_and_never_fabricates():
    item = _labels(ContextBand.small, ContextBand.large)
    assert needs_adjudication(item)
    assert resolve(item) is None  # no decision -> unresolved, no invented band
    decision = Adjudication("chief", ContextBand.medium, False, "boundary call", 0.6)
    out = resolve(item, adjudication=decision)
    assert out.band is ContextBand.medium and out.adjudicated_by == "chief"


def test_mixed_abstain_and_band_is_a_disagreement():
    item = _labels(ContextBand.small, None, b_abstain=True)
    assert needs_adjudication(item)


# --- splits -----------------------------------------------------------------


def _item(cid: str, prompt: str, band: ContextBand) -> AdjudicatedItem:
    return AdjudicatedItem(
        id=cid,
        prompt=prompt,
        category="coding",
        band=band,
        label_source="generated_candidate",
        rationale="r",
        confidence=0.7,
    )


def test_partition_is_deterministic_and_labels_split():
    items = [_item(f"i{n}", f"unique prompt number {n} here", ContextBand.small) for n in range(30)]
    r1 = partition(items)
    r2 = partition(items)
    assert [i.id for i in r1.dev] == [i.id for i in r2.dev]
    assert all(i.split == "dev" for i in r1.dev)
    total = len(r1.train) + len(r1.dev) + len(r1.holdout)
    assert total == 30


def test_near_duplicates_never_straddle_splits():
    items = [
        _item("a", "reindex the entire search cluster tonight", ContextBand.large),
        _item("b", "reindex the entire search cluster today", ContextBand.large),
    ] + [_item(f"f{n}", f"filler prompt {n} distinct words", ContextBand.small) for n in range(20)]
    r = partition(items)
    for split in r.as_dict().values():
        ids = {i.id for i in split}
        assert not ({"a", "b"} & ids) or {"a", "b"} <= ids  # both together or neither


def test_partition_refuses_frozen_holdout_leak():
    frozen = _frozen_prompts()
    # force one item to be an exact frozen-holdout prompt
    items = [_item("leak", frozen[0], ContextBand.small)] + [
        _item(f"x{n}", f"clean distinct prompt {n}", ContextBand.small) for n in range(20)
    ]
    with pytest.raises(LeakageError):
        partition(
            items, frozen_holdout_prompts=frozen, ratios={"train": 0.0, "dev": 0.0, "holdout": 1.0}
        )


# --- comparison -------------------------------------------------------------


def test_predict_strategies_return_valid_bands():
    for strat in ("rules", "learned", "hybrid"):
        p = predict("Write a tiny function to add two numbers.", strat)
        assert p.band in set(ContextBand)
        assert 0.0 <= p.confidence <= 1.0


def test_compare_all_reports_every_strategy_and_metrics():
    items = [
        _item("s1", "print hello world once", ContextBand.small),
        _item("s2", "add two integers together", ContextBand.small),
        _item("l1", "analyze 140k tokens of gateway logs for anomalies", ContextBand.large),
        AdjudicatedItem(
            id="ab",
            prompt="do the thing",
            category="ambiguous",
            abstained=True,
            label_source="generated_candidate",
            rationale="ambiguous",
            confidence=0.3,
        ),
    ]
    reports = compare_all(items)
    assert set(reports) == {"rules", "learned", "hybrid"}
    for r in reports.values():
        assert 0.0 <= r.accuracy <= 1.0
        assert 0.0 <= r.macro_f1 <= 1.0
        assert r.abstained_items == 1  # abstained item excluded from accuracy, counted
        assert set(r.per_band_recall) == {b.value for b in ContextBand}


# --- optional Graphify impact signal ----------------------------------------


def test_graph_signal_text_only_fallback_when_absent(tmp_path):
    sig = graph_signals.impact_for("refactor the parser", graph_path=tmp_path / "nope.json")
    assert sig.available is False
    assert sig.feature == 0.0  # text-only fallback never fabricates impact


def test_graph_signal_scores_matched_repository_artifacts(tmp_path):
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [{"id": "classifier"}, {"id": "engine"}, {"id": "hosts"}],
                "edges": [{"source": "classifier", "target": "engine"}],
            }
        ),
        encoding="utf-8",
    )
    hit = graph_signals.impact_for("audit the classifier module", graph_path=graph)
    assert hit.available is True and hit.matched_nodes >= 1
    miss = graph_signals.impact_for("write a limerick", graph_path=graph)
    assert miss.available is True and miss.matched_nodes == 0 and miss.feature == 0.0
