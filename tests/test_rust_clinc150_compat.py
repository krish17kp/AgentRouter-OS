"""Differential parity for CLINC150 raw-row normalization."""

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


def _rust_cases(label_names: list[str], rows: list[dict]) -> list[dict]:
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
        input=json.dumps({"label_names": label_names, "rows": rows}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    "label_names,rows",
    [
        (
            ["translate", "text_translate", "unsupported", "oos", "calendar"],
            [
                {"text": "  Translate this phrase  ", "intent": 0},
                {"text": "Translate this phrase", "intent": 2},
                {"text": "Please translate the text", "intent": 1},
                {"text": "A novel unsupported request", "intent": 2},
                {"text": "I am outside scope", "intent": 3},
                {"text": "Could you add an event?", "intent": 4},
            ],
        ),
        (
            [
                "definition",
                "spelling",
                "calculator",
                "math",
                "how_busy",
                "meaning_of_life",
                "todo",
                "reminder",
            ],
            [
                {"text": f"request for {intent}", "intent": index}
                for index, intent in enumerate(
                    [
                        "definition",
                        "spelling",
                        "calculator",
                        "math",
                        "how_busy",
                        "meaning_of_life",
                        "todo",
                        "reminder",
                    ]
                )
            ],
        ),
    ],
)
def test_rust_clinc150_raw_transform_matches_python(label_names, rows, monkeypatch):
    class Dataset(list):
        features = {"intent": type("Feature", (), {"names": label_names})()}

    adapter = CLINC150Adapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(adapter, "_hf_load", lambda split: Dataset(rows))
    expected = [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]
    assert _rust_cases(label_names, rows) == expected
