"""Evaluator facade exports and packaged model seed loading match Python."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import evaluators

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_evaluator_facade_and_seed_models_match_python():
    environment = os.environ.copy()
    target = Path(environment.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
    subprocess.run(
        ["cargo", "build", "--quiet", "--locked", "-p", "agentrouter-cli", "--bin", "agentrouter"],
        cwd=ROOT,
        env=environment,
        timeout=120,
        check=True,
    )
    environment["PATH"] = f"{target}{os.pathsep}{environment.get('PATH', '')}"
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
        env=environment,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = [model.model_dump(mode="json") for model in evaluators.load_seed_models()]
    assert actual["models"] == expected
    assert actual["exports"] == evaluators.__all__
    assert actual["provider_default"] == evaluators.evaluate_provider()
    expected_platform = evaluators.evaluate_platform()
    actual_platform = actual["platform_default"]
    assert actual_platform["score"] == expected_platform["score"]
    for field in ("expected", "present", "missing"):
        assert actual_platform["detail"][field] == expected_platform["detail"][field]
    assert set(actual_platform["detail"]["groups_found"]) == set(
        expected_platform["detail"]["groups_found"]
    ) - {"contract"}
    performance = actual["performance_default"]
    assert 0.0 <= performance["score"] <= 1.0
    assert performance["detail"]["n_samples"] == 8
