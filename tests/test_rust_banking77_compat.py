"""Differential parity for Banking77 raw-row normalization."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.banking77 import Banking77Adapter

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
            "evaluation_banking77_from_json",
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
            ["cash withdrawal", "cash deposit", "cash withdrawal"],
            [
                {"text": "  Where is my cash withdrawal? ", "label": 0},
                {"text": "Where is my cash withdrawal?", "label": 1},
                {"text": "where is my cash withdrawal", "label": 2},
                {"text": "Can I deposit a cheque?", "label": 1},
            ],
        ),
        (
            ["cash withdrawal", "cash deposit"],
            [
                {"text": "My card was swallowed", "label": 0},
                {"text": "The ATM took my card", "label": 1},
            ],
        ),
    ],
)
def test_rust_banking77_raw_transform_matches_python(label_names, rows, monkeypatch):
    class Dataset(list):
        features = {"label": type("Feature", (), {"names": label_names})()}

    adapter = Banking77Adapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(adapter, "_hf_load", lambda split: Dataset(rows))
    expected = [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]
    assert _rust_cases(label_names, rows) == expected
