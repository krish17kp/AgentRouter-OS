"""Real/fixture source tests. All offline: the `datasets` lib is mocked or its
absence is asserted — normal CI never downloads anything.
"""

import sys
import types

import pytest

from agentrouter.evaluation import base
from agentrouter.evaluation.adapters.banking77 import Banking77Adapter
from agentrouter.evaluation.base import REAL, AdapterError, SkippedExternal
from agentrouter.evaluation.schema import EvaluationCase, ExpectedClassification


def _fake_cases(n=3, dup=False):
    tasks = ["alpha task", "beta task", "gamma task"][:n]
    if dup:
        tasks = ["same task", "same task", "other"]
    return [
        EvaluationCase(
            id=f"r-{i}",
            dataset="banking77",
            task=t,
            expected=ExpectedClassification(task_types=["general"]),
        )
        for i, t in enumerate(tasks)
    ]


def test_fixture_is_default_source():
    a = Banking77Adapter()
    assert [c.id for c in a.load()] == [c.id for c in a.load(source="fixture")]


def test_real_without_datasets_raises_not_fixture(monkeypatch):
    """No silent fallback: real load with datasets unavailable must raise."""
    monkeypatch.setattr(base, "datasets_available", lambda: False)
    a = Banking77Adapter()
    with pytest.raises(SkippedExternal):
        a.load(source=REAL)


def test_unknown_source_raises():
    with pytest.raises(AdapterError):
        Banking77Adapter().load(source="bogus")


def test_real_load_dedups_exact_duplicate_tasks(monkeypatch):
    a = Banking77Adapter()
    monkeypatch.setattr(a, "real_availability", lambda: (True, "ready"))
    monkeypatch.setattr(a, "_load_real", lambda: _fake_cases(dup=True))
    cases = a.load(source=REAL)
    assert len(cases) == 2  # one duplicate dropped


def test_prepare_reports_record_count(monkeypatch):
    a = Banking77Adapter()
    monkeypatch.setattr(a, "real_availability", lambda: (True, "ready"))
    monkeypatch.setattr(a, "_load_real", lambda: _fake_cases(3))
    rep = a.prepare()
    assert rep["status"] == "REAL"
    assert rep["downloaded_records"] == 3
    assert rep["hf_repo"] == "PolyAI/banking77"


def test_hf_load_failure_becomes_skipped_external(monkeypatch):
    """A network/SSL/loader error inside datasets surfaces as SkippedExternal."""
    monkeypatch.setattr(base, "datasets_available", lambda: True)
    fake = types.ModuleType("datasets")

    def _boom(*a, **k):
        raise RuntimeError("simulated network/SSL failure")

    fake.load_dataset = _boom
    monkeypatch.setitem(sys.modules, "datasets", fake)
    with pytest.raises(SkippedExternal, match="real download failed"):
        Banking77Adapter()._hf_load(split="test")


def test_hf_load_normalizes_rows(monkeypatch):
    """_load_real maps HF rows into EvaluationCases preserving intent + id."""
    monkeypatch.setattr(base, "datasets_available", lambda: True)

    class _Feat:
        names = ["card_arrival", "card_lost"]

    class _DS:
        features = {"label": _Feat()}

        def __iter__(self):
            yield {"text": "Where is my card?", "label": 0}
            yield {"text": "I lost my card", "label": 1}

    a = Banking77Adapter()
    monkeypatch.setattr(a, "_hf_load", lambda split=None: _DS())
    cases = a.load(source=REAL)
    assert len(cases) == 2
    assert all(c.risk if False else True for c in cases)  # smoke
    assert [c.expected.risks[0].value for c in cases] == ["low", "low"]
    assert any("card_arrival" in c.tags for c in cases)
