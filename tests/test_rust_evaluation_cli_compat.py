"""Smoke and contract coverage for the Rust evaluation CLI executable."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.runner import run as python_run

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
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
        env=process_env,
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


def test_rust_evaluation_cli_honors_relocated_project_root(tmp_path):
    relocated = tmp_path / "relocated"
    shutil.copytree(
        ROOT / "agentrouter" / "evaluation" / "fixtures",
        relocated / "agentrouter/evaluation/fixtures",
    )
    benchmarks = relocated / "agentrouter/benchmarks"
    benchmarks.mkdir(parents=True)
    shutil.copy2(
        ROOT / "agentrouter" / "benchmarks" / "classifier_gold_v1.yaml",
        benchmarks / "classifier_gold_v1.yaml",
    )
    process = _cli("list-datasets", "--json", env={"AGENTROUTER_PROJECT_ROOT": str(relocated)})
    assert process.returncode == 0, process.stderr
    rows = json.loads(process.stdout)
    assert len(rows) == 8
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


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--dataset", "agentrouter-gold", "--profile", "nightly"],
    ],
)
def test_rust_evaluation_cli_run_matches_python_profile_normalization(arguments):
    process = _cli("run", *arguments, "--limit", "2", "--no-artifacts", "--json")
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    if "--dataset" in arguments:
        expected = python_run(dataset="agentrouter-gold", limit=2)
    else:
        expected = python_run(profile="fast", limit=2)
    for report in (actual, expected):
        report.pop("environment")
        report.pop("classification", None)
    assert actual == expected


def test_rust_evaluation_cli_empty_languages_matches_python_no_filter():
    process = _cli(
        "run",
        "--dataset",
        "massive",
        "--languages",
        "",
        "--limit",
        "3",
        "--seed",
        "5",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = python_run(dataset="massive", limit=3, seed=5)
    for report in (actual, expected):
        report.pop("environment")
        report.pop("classification", None)
    assert actual == expected


def test_rust_evaluation_cli_accepts_negative_limit_like_python():
    process = _cli(
        "run",
        "--dataset",
        "agentrouter-gold",
        "--limit",
        "-1",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = python_run(dataset="agentrouter-gold", limit=-1)
    for report in (actual, expected):
        report.pop("environment")
        report.pop("classification", None)
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


def test_rust_evaluation_cli_context_band_text_matches_python_formatting():
    process = _cli("context-band-generalization")
    assert process.returncode == 0, process.stderr
    assert 'Holdout SHA-256: "' not in process.stdout
    assert "95% bootstrap CI" in process.stdout
    assert "Per-band recall: {" in process.stdout
    assert "Accuracy delta: +" in process.stdout


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

    unknown = _cli("prepare", "--dataset", "does-not-exist")
    assert unknown.returncode == 1
    assert "does-not-exist" in unknown.stdout
    assert "UNAVAILABLE (adapter not importable)" in unknown.stdout

    unknown_json = _cli("prepare", "--dataset", "does-not-exist", "--json")
    assert unknown_json.returncode == 1
    assert json.loads(unknown_json.stdout) == [
        {
            "dataset": "does-not-exist",
            "status": "UNAVAILABLE",
            "blocker": "adapter not importable",
        }
    ]

    all_unavailable = _cli("prepare", "--all")
    assert all_unavailable.returncode == 0, all_unavailable.stderr
    assert all_unavailable.stdout.count("SKIPPED_EXTERNAL") == 8

    status_json = _cli("status", "--json")
    assert status_json.returncode == 0, status_json.stderr
    status_rows = json.loads(status_json.stdout)
    assert len(status_rows) == 8
    gold_status = next(row for row in status_rows if row["dataset"] == "agentrouter-gold")
    assert gold_status["fixture"] is True
    assert gold_status["real"] is False
    assert "no real loader configured" in gold_status["blocker"]

    prepare_json = _cli("prepare", "--all", "--json")
    assert prepare_json.returncode == 0, prepare_json.stderr
    prepare_rows = json.loads(prepare_json.stdout)
    assert len(prepare_rows) == 8
    assert all(row["status"] == "SKIPPED_EXTERNAL" for row in prepare_rows)


def test_rust_evaluation_validate_dataset_error_prefix_matches_python():
    process = _cli("validate-dataset", "does-not-exist")
    assert process.returncode == 3
    assert process.stderr.startswith("Invalid dataset:")


def test_rust_evaluation_status_uses_fixture_presence_not_record_count(tmp_path):
    relocated = tmp_path / "relocated"
    shutil.copytree(
        ROOT / "agentrouter" / "evaluation" / "fixtures",
        relocated / "agentrouter/evaluation/fixtures",
    )
    benchmarks = relocated / "agentrouter/benchmarks"
    benchmarks.mkdir(parents=True)
    shutil.copy2(
        ROOT / "agentrouter" / "benchmarks" / "classifier_gold_v1.yaml",
        benchmarks / "classifier_gold_v1.yaml",
    )
    # An empty fixture is still present and therefore fixture-only in Python's
    # adapter contract; status must not infer availability from record count.
    (relocated / "agentrouter/evaluation/fixtures/massive_sample.jsonl").write_text(
        "", encoding="utf-8"
    )
    process = _cli("status", "--json", env={"AGENTROUTER_PROJECT_ROOT": str(relocated)})
    assert process.returncode == 0, process.stderr
    rows = json.loads(process.stdout)
    massive = next(row for row in rows if row["dataset"] == "massive")
    assert massive["fixture"] is True


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
