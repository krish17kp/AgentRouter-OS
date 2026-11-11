"""Differential coverage for the composed Rust seven-dimension scorecard."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.evaluators.platform import _command_names, _group_names
from agentrouter.evaluation.grading import grade

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_measure_all_scorecard_matches_python_dimensions():
    cases = AgentRouterGoldAdapter().load()[:12]
    request = {
        "cases": [case.model_dump(mode="json") for case in cases],
        "commands": sorted(_command_names()),
        "groups": sorted(_group_names()),
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_grade_all_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    actual = json.loads(process.stdout)
    expected = grade(cases, measure_all=True)

    assert actual["classification"] == expected["classification"]
    assert actual["release_gates"] == expected["release_gates"]
    assert actual["release_ready"] == expected["release_ready"]
    assert actual["dimensions"].keys() == expected["dimensions"].keys()
    for dimension, expected_value in expected["dimensions"].items():
        actual_value = actual["dimensions"][dimension]
        assert actual_value["weight"] == expected_value["weight"]
        assert actual_value["status"] == expected_value["status"]
        assert actual_value["score"] == expected_value["score"]
        assert actual_value["achieved"] == expected_value["achieved"]
        if dimension != "performance":
            assert actual_value["detail"] == expected_value["detail"]

    assert actual["possible_measured_points"] == 100
    assert actual["grade_over_100"] == expected["grade_over_100"]
    assert actual["achieved_points"] == expected["achieved_points"]
    assert actual["dimensions"]["performance"]["detail"]["n_samples"] == 8
    assert actual["dimensions"]["performance"]["score"] == expected["dimensions"][
        "performance"
    ]["score"]
