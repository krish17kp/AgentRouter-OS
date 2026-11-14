"""Differential parity for MASSIVE locale-aware raw-row normalization."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.massive import MassiveAdapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
ROWS = {
    "en-US": [
        {
            "utt": "  Hello, World!  ",
            "scenario": "banking",
            "intent": "greeting",
            "category": 12,
        },
        {"utt": "hello, world!", "scenario": "duplicate", "intent": "other"},
        {"utt": "hello world", "scenario": "near duplicate", "intent": "other"},
        {"utt": "An English query", "intent": None},
    ],
    "hi-IN": [
        {"utt": "The same prompt", "scenario": 2, "intent": 10},
        {"utt": "A Hindi query", "scenario": None},
    ],
    "fr-FR": [{"utt": "Un texte français", "scenario": "travel", "intent": "translate"}],
}


def _rust_cases(languages: list[str] | None) -> list[dict] | dict:
    payload = {"languages": languages, "datasets": ROWS}
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_massive_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize("languages", [None, ["fr", "en"], ["hi"]])
def test_rust_massive_rows_match_python(languages, monkeypatch):
    adapter = MassiveAdapter(languages=languages)

    class Dataset(list):
        def __init__(self, rows):
            super().__init__(rows)
            self.features = {}

    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(adapter, "_hf_load", lambda split: Dataset(ROWS[adapter.hf_config]))
    expected = [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]
    assert _rust_cases(languages) == expected


def test_rust_massive_unknown_language_matches_python_skip(monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    adapter = MassiveAdapter(languages=["xx"])
    with pytest.raises(evaluation_base.SkippedExternal) as exc_info:
        adapter.load(source=evaluation_base.REAL)
    assert _rust_cases(["xx"]) == {"error": str(exc_info.value)}
