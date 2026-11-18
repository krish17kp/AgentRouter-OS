"""Differential contract checks for CLINC150 real-row normalization."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.clinc150 import CLINC150Adapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


class _Dataset(list):
    def __init__(self, rows: list[dict], intent_names: list[str]):
        super().__init__(rows)
        self.features = {"intent": type("Feature", (), {"names": intent_names})()}


def _rust_cases(intent_names: list[str], rows: list[dict]) -> list[dict]:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_clinc150_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"label_names": intent_names, "rows": rows}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def _python_cases(intent_names: list[str], rows: list[dict], monkeypatch) -> list[dict]:
    adapter = CLINC150Adapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_hf_load",
        lambda split: _Dataset(rows, intent_names),
    )
    return [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]


@pytest.mark.parametrize(
    "intent_names",
    [
        [
            "translate",
            "definition",
            "spelling",
            "calculator",
            "math",
            "how_busy",
            "meaning_of_life",
            "text",
            "todo",
            "reminder",
            "calendar",
            "oos",
            "unmapped_intent",
        ],
        ["definition_translate", "unknown", "oos"],
    ],
)
def test_rust_clinc150_intent_mapping_matches_python(intent_names, monkeypatch):
    rows = [
        {"text": f"How do I handle {intent}?", "intent": index}
        for index, intent in enumerate(intent_names)
    ]
    assert _rust_cases(intent_names, rows) == _python_cases(intent_names, rows, monkeypatch)


def test_rust_clinc150_ordered_mapping_and_dedup_match_python(monkeypatch):
    intent_names = ["definition_translate", "spelling", "oos"]
    rows = [
        {"text": "  Explain this definition! ", "intent": 0},
        {"text": "explain this definition!", "intent": 1},
        {"text": "Explain this definition", "intent": 1},
        {"text": "¿Qué hora es?", "intent": 2},
        {"text": "¿Qué hora es?", "intent": 1},
    ]
    assert _rust_cases(intent_names, rows) == _python_cases(intent_names, rows, monkeypatch)
