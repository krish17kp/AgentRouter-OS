"""Differential parity for LongBench v2 row preparation and buckets."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.longbench_v2 import LongBenchV2Adapter, bucket_for

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
BUCKET_TOKENS = [
    -1,
    0,
    7_999,
    8_000,
    31_999,
    32_000,
    127_999,
    128_000,
    511_999,
    512_000,
    999_999_999,
    1_000_000_000,
]
ROWS = [
    {"question": "  ", "context": "ignored"},
    {"question": " What does this report say? ", "context": "word " * 6_154},
    {"question": "what does this report say?", "context": "duplicate"},
    {
        "_id": 17,
        "question": "How will this work?",
        "context": "word " * 24_616,
        "domain": None,
        "difficulty": True,
    },
    {"question": "How, will this work", "context": "a short context"},
    {"_id": None, "question": "A final short question", "context": "", "domain": 3},
]


def _rust_surface() -> dict:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_longbench_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"rows": ROWS, "bucket_tokens": BUCKET_TOKENS}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def test_rust_longbench_row_normalization_matches_python(monkeypatch):
    adapter = LongBenchV2Adapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(adapter, "_hf_load", lambda split: ROWS)
    expected = [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]
    actual = _rust_surface()
    assert actual["cases"] == expected
    assert actual["buckets"] == [bucket_for(tokens) for tokens in BUCKET_TOKENS]
