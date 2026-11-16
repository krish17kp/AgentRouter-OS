"""Contract coverage for Rust's no-manifest public grading runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.classifier import classify
from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.grading import grade

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
CARGO = shutil.which("cargo") or "cargo"
_MISSING = object()


def _runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    target = Path(environment.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
    environment["PATH"] = f"{target}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def _default_grade(
    cases,
    *,
    measure_all: bool,
    context_band_generalization=_MISSING,
    prediction=None,
    environment=None,
    check=True,
):
    request = {
        "cases": [case.model_dump(mode="json") for case in cases],
        "measure_all": measure_all,
    }
    if context_band_generalization is not _MISSING:
        request["context_band_generalization"] = context_band_generalization
    if prediction is not None:
        request["prediction"] = prediction.model_dump(mode="json")
    command = [
        CARGO,
        "run",
        "--quiet",
        "--locked",
        "--bin",
        "evaluation_default_grade_from_json",
        "-p",
        "agentrouter-evaluation",
    ]
    if environment is not None:
        subprocess.run(
            [
                CARGO,
                "build",
                "--quiet",
                "--locked",
                "--bin",
                "evaluation_default_grade_from_json",
                "-p",
                "agentrouter-evaluation",
            ],
            cwd=ROOT,
            timeout=120,
            check=True,
        )
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
        suffix = ".exe" if os.name == "nt" else ""
        command = [str(target / f"evaluation_default_grade_from_json{suffix}")]
    process = subprocess.run(
        command,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=environment or _runtime_environment(),
        timeout=120,
        check=check,
    )
    return json.loads(process.stdout) if check else process


def _rust_cli_surface() -> dict:
    subprocess.run(
        [
            CARGO,
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
            CARGO,
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

    assert actual == expected


def test_default_runtime_discovers_models_and_cli_for_all_dimensions():
    cases = AgentRouterGoldAdapter().load()[:12]
    surface = _rust_cli_surface()
    actual = _default_grade(cases, measure_all=True)
    expected = grade(cases, measure_all=True)

    for report in (actual, expected):
        performance = report["dimensions"]["performance"]["detail"]
        performance.pop("classify_median_ms")
        performance.pop("route_median_ms")
    assert actual == expected
    platform = actual["dimensions"]["cli_platform"]["detail"]
    assert platform["commands_found"] == surface["commands"]
    assert platform["groups_found"] == sorted([*surface["groups"], "contract"])
    assert actual["dimensions"]["performance"]["detail"]["n_samples"] == 8


def test_default_runtime_supports_empty_cases_and_context_override():
    cases = []
    context_report = {"current_holdout": {"accuracy": 0.0}}
    actual = _default_grade(cases, measure_all=False, context_band_generalization=context_report)
    expected = grade(cases, context_band_generalization=context_report)

    _assert_scorecard_fields(actual, expected)
    assert actual["context_band_generalization"] == context_report


@pytest.mark.parametrize("measure_all", [False, True])
def test_default_runtime_propagates_injected_classifier(measure_all):
    cases = AgentRouterGoldAdapter().load()[:12]
    prediction = classify("Write a short summary of this document")
    actual = _default_grade(cases, measure_all=measure_all, prediction=prediction)
    expected = grade(cases, classify_fn=lambda _: prediction, measure_all=measure_all)

    if not measure_all:
        assert actual == expected
        return
    for report in (actual, expected):
        performance = report["dimensions"]["performance"]["detail"]
        performance.pop("classify_median_ms")
        performance.pop("route_median_ms")
    assert actual == expected


@pytest.mark.parametrize("measure_all", [False, True])
def test_default_runtime_explicit_null_context_matches_absent(measure_all):
    cases = AgentRouterGoldAdapter().load()[:3]
    absent = _default_grade(cases, measure_all=measure_all)
    explicit_null = _default_grade(cases, measure_all=measure_all, context_band_generalization=None)
    if not measure_all:
        assert explicit_null == absent
        return
    for report in (absent, explicit_null):
        detail = report["dimensions"]["performance"]["detail"]
        detail.pop("classify_median_ms")
        detail.pop("route_median_ms")
    assert explicit_null == absent


@pytest.mark.parametrize("measure_all", [False, True])
@pytest.mark.parametrize(
    "malformed",
    [
        {},
        {"current_holdout": None},
        {"current_holdout": {"accuracy": None}},
        {"current_holdout": {"accuracy": "0.9"}},
    ],
)
def test_default_runtime_rejects_malformed_context_evidence(measure_all, malformed):
    process = _default_grade(
        [],
        measure_all=measure_all,
        context_band_generalization=malformed,
        check=False,
    )
    assert process.returncode != 0
    assert not process.stdout.strip()


def _fixture_cli_environment(tmp_path: Path, mode: str) -> dict[str, str]:
    subprocess.run(
        [
            CARGO,
            "build",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-evaluation",
            "--bin",
            "evaluation_cli_surface_fixture",
        ],
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    environment = os.environ.copy()
    target = Path(environment.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
    suffix = ".exe" if os.name == "nt" else ""
    shutil.copy2(
        target / f"evaluation_cli_surface_fixture{suffix}", tmp_path / f"agentrouter{suffix}"
    )
    environment["AGENTROUTER_EVALUATION_CLI"] = str(tmp_path / f"agentrouter{suffix}")
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment.get('PATH', '')}"
    environment["AGENTROUTER_TEST_SURFACE_MODE"] = mode
    return environment


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("nonzero", "could not report its command surface"),
        ("malformed", "returned an invalid surface"),
        ("unknown-field", "returned an invalid surface"),
    ],
)
def test_default_runtime_fails_closed_on_installed_cli_process_errors(tmp_path, mode, message):
    process = _default_grade(
        [],
        measure_all=True,
        environment=_fixture_cli_environment(tmp_path, mode),
        check=False,
    )
    assert process.returncode != 0
    assert message in process.stderr


def test_default_runtime_fails_closed_when_installed_cli_is_missing(tmp_path):
    environment = os.environ.copy()
    environment["PATH"] = str(tmp_path)
    environment["AGENTROUTER_EVALUATION_CLI"] = str(tmp_path / "missing-agentrouter")
    process = _default_grade([], measure_all=True, environment=environment, check=False)
    assert process.returncode != 0
    assert "could not query the installed Rust CLI surface" in process.stderr
