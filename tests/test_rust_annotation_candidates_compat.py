"""Differential coverage for deterministic unlabelled candidate generation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.candidates import _all_unique, generate

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(operation: str, *, count=None, seed=20260731):
    payload = {"operation": operation, "seed": str(seed), "count": count}
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_candidates_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _dump(values):
    return [value.model_dump(mode="json") for value in values]


def test_rust_candidate_bank_matches_all_python_templates_in_order():
    process = _rust("bank")
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [
        {"category": category, "scope": scope, "prompt": prompt}
        for category, scope, prompt in _all_unique()
    ]


@pytest.mark.parametrize("seed", [0, 20260731, -17, 2**40 + 3, 2**80 + 17])
@pytest.mark.parametrize("count", [None, 0, 1, 11, 62, 63, 80, -1, -64, -100])
def test_rust_candidate_generation_matches_python(seed, count):
    expected = _dump(generate(count, seed=seed))
    process = _rust("generate", count=count, seed=seed)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected
