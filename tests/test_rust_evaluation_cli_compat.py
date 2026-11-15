"""Smoke and contract coverage for the Rust evaluation CLI executable."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.runner import run as python_run

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "agentrouter-evaluate",
            "-p",
            "agentrouter-evaluation",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def test_rust_evaluation_cli_lists_registered_datasets():
    process = _cli("list-datasets", "--json")
    assert process.returncode == 0, process.stderr
    rows = json.loads(process.stdout)
    assert [row["name"] for row in rows] == [
        "agentrouter-gold",
        "clinc150",
        "banking77",
        "massive",
        "longbench-v2",
        "swebench",
        "llmrouterbench",
        "twinrouterbench",
    ]
    assert all(row["availability"] in {"ready", "fixture_only", "skipped_external"} for row in rows)


def test_rust_evaluation_cli_run_matches_python_report_without_artifacts():
    process = _cli(
        "run",
        "--dataset",
        "agentrouter-gold",
        "--limit",
        "7",
        "--seed",
        "12",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = python_run(dataset="agentrouter-gold", limit=7, seed=12)
    expected.pop("environment")
    expected.pop("classification")
    actual.pop("environment")
    assert actual == expected


def test_rust_evaluation_cli_reports_external_blocker_without_fixture_fallback():
    process = _cli(
        "run",
        "--dataset",
        "clinc150",
        "--source",
        "real",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["n_cases"] == 0
    assert result["datasets"]["clinc150"]["status"] == "SKIPPED_EXTERNAL"
    assert "fixture_only" in result["datasets"]["clinc150"]["availability"]
    assert result["datasets"]["clinc150"]["blocker"]


def test_rust_evaluation_cli_rejects_incomplete_release_gate_request():
    process = _cli("run", "--require-release-ready", "--no-artifacts", "--json")
    assert process.returncode == 2
    assert "requires --all" in process.stderr


@pytest.mark.parametrize("command", ["list-datasets", "context-band-generalization"])
def test_rust_evaluation_cli_rejects_unknown_readonly_command_options(command):
    process = _cli(command, "--unexpected")
    assert process.returncode == 2
    assert "unknown option --unexpected" in process.stderr


def test_rust_evaluation_cli_context_band_json_contract():
    process = _cli("context-band-generalization", "--json")
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["holdout_sha256"]
    assert "current_holdout" in payload


def test_rust_evaluation_cli_status_and_prepare_contracts():
    status = _cli("status")
    assert status.returncode == 0, status.stderr
    assert "agentrouter-gold" in status.stdout

    missing_selection = _cli("prepare")
    assert missing_selection.returncode == 2
    assert "--dataset" in missing_selection.stderr

    unavailable = _cli("prepare", "--dataset", "agentrouter-gold")
    assert unavailable.returncode == 1
    assert "SKIPPED_EXTERNAL" in unavailable.stdout


def test_rust_evaluation_cli_report_and_compare_artifacts(tmp_path):
    baseline_dir = tmp_path / "baseline"
    current_dir = tmp_path / "current"
    for directory in (baseline_dir, current_dir):
        process = _cli(
            "run",
            "--dataset",
            "agentrouter-gold",
            "--limit",
            "7",
            "--out-dir",
            str(directory),
        )
        assert process.returncode == 0, process.stderr

    report = _cli("report", str(baseline_dir / "result.json"))
    assert report.returncode == 0, report.stderr
    assert "# Evaluation report" in report.stdout

    output = tmp_path / "comparison"
    comparison = _cli(
        "compare",
        str(baseline_dir / "result.json"),
        str(current_dir / "result.json"),
        "--out-dir",
        str(output),
    )
    assert comparison.returncode == 0, comparison.stderr
    assert "Critical regression: NO" in comparison.stdout
    assert (output / "comparison.md").is_file()


def test_rust_evaluation_cli_missing_report_and_compare_inputs_fail_closed(tmp_path):
    missing = tmp_path / "missing.json"
    report = _cli("report", str(missing))
    assert report.returncode == 3
    assert "Not found" in report.stderr

    comparison = _cli("compare", str(missing), str(missing))
    assert comparison.returncode == 3
    assert "Not found" in comparison.stderr


@pytest.mark.parametrize("command", [("report",), ("compare",), ("compare", "one.json")])
def test_rust_evaluation_cli_missing_required_paths_are_usage_errors(command):
    process = _cli(*command)
    assert process.returncode == 2
    assert "needs" in process.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ("report", "missing.json", "--unexpected"),
        ("status", "--dataset", "agentrouter-gold"),
        ("status", "--all"),
        ("status", "--limit", "1"),
    ],
)
def test_rust_evaluation_cli_rejects_python_incompatible_extra_options(arguments):
    process = _cli(*arguments)
    assert process.returncode == 2
    assert "unknown option" in process.stderr
