"""Contract coverage for Rust's no-manifest public grading runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.grading import grade

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    target = Path(environment.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
    environment["PATH"] = f"{target}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def _default_grade(cases, *, measure_all: bool, context_band_generalization=None) -> dict:
    request = {
        "cases": [case.model_dump(mode="json") for case in cases],
        "measure_all": measure_all,
    }
    if context_band_generalization is not None:
        request["context_band_generalization"] = context_band_generalization
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_default_grade_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=_runtime_environment(),
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def _rust_cli_surface() -> dict:
    subprocess.run(
        [
            "cargo",
            "build",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "agentrouter",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "agentrouter",
            "--",
            "__evaluation_surface",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def _assert_scorecard_fields(actual: dict, expected: dict) -> None:
    for field in (
        "n_cases",
        "classification",
        "release_gates",
        "release_ready",
        "achieved_points",
        "possible_measured_points",
        "grade_over_100",
        "grade_of_measured",
    ):
        assert actual[field] == expected[field]
    assert actual["dimensions"] == expected["dimensions"]


def test_default_runtime_matches_python_classification_only_without_manifests():
    cases = AgentRouterGoldAdapter().load()[:12]
    actual = _default_grade(cases, measure_all=False)
    expected = grade(cases)

    _assert_scorecard_fields(actual, expected)
    assert actual["environment"] is None
    assert actual["datasets"] is None
    assert actual["source"] == "runtime"


def test_default_runtime_discovers_models_and_cli_for_all_dimensions():
    cases = AgentRouterGoldAdapter().load()[:12]
    surface = _rust_cli_surface()
    actual = _default_grade(cases, measure_all=True)
    expected = grade(cases, measure_all=True)

    for field in (
        "n_cases",
        "classification",
        "release_gates",
        "release_ready",
        "achieved_points",
        "possible_measured_points",
        "grade_over_100",
        "grade_of_measured",
    ):
        assert actual[field] == expected[field]
    for dimension, expected_dimension in expected["dimensions"].items():
        actual_dimension = actual["dimensions"][dimension]
        for field in ("weight", "status", "score", "achieved"):
            assert actual_dimension[field] == expected_dimension[field]
        if dimension not in {"cli_platform", "performance"}:
            assert actual_dimension["detail"] == expected_dimension["detail"]
    platform = actual["dimensions"]["cli_platform"]["detail"]
    assert platform["commands_found"] == surface["commands"]
    assert platform["groups_found"] == surface["groups"]
    assert actual["dimensions"]["performance"]["detail"]["n_samples"] == 8


def test_default_runtime_supports_empty_cases_and_context_override():
    cases = []
    context_report = {"current_holdout": {"accuracy": 0.0}}
    actual = _default_grade(
        cases, measure_all=False, context_band_generalization=context_report
    )
    expected = grade(cases, context_band_generalization=context_report)

    _assert_scorecard_fields(actual, expected)
    assert actual["context_band_generalization"] == context_report
