"""Evaluator facade exports and packaged model seed loading match Python."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import evaluators

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_evaluator_facade_and_seed_models_match_python():
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_evaluators_api_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = [model.model_dump(mode="json") for model in evaluators.load_seed_models()]
    assert actual["models"] == expected
    assert actual["exports"] == evaluators.__all__
