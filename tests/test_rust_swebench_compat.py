"""Differential parity for SWE-bench issue-row preparation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.swebench import SWEBenchAdapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
ROWS = [
    {"problem_statement": "  "},
    {
        "instance_id": "django-12",
        "problem_statement": "  Fix the race in the request handler  ",
        "repo": "org/project",
        "base_commit": "abc123",
        "version": "ignored by adapter",
    },
    {
        "instance_id": "duplicate",
        "problem_statement": "fix the race in the request handler",
        "repo": "org/other",
    },
    {
        "instance_id": "near-duplicate",
        "problem_statement": "Fix the race in the request handler!!!",
    },
    {"problem_statement": "A separate issue needs investigation"},
    {
        "instance_id": None,
        "problem_statement": "A final issue with explicit null metadata",
        "repo": None,
        "base_commit": None,
    },
]


def _rust_cases() -> list[dict]:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_swebench_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"rows": ROWS}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def test_rust_swebench_row_normalization_matches_python(monkeypatch):
    adapter = SWEBenchAdapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: True)
    monkeypatch.setattr(adapter, "_hf_load", lambda split: ROWS)
    expected = [case.model_dump(mode="json") for case in adapter.load(source=evaluation_base.REAL)]
    assert _rust_cases() == expected
