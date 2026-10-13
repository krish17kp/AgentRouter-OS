"""Tests for the `agentrouter eval` CLI sub-app."""

import json

from typer.testing import CliRunner

from agentrouter.cli import app
from agentrouter.evaluation import cli as evaluation_cli

runner = CliRunner()


def test_list_datasets_runs():
    r = runner.invoke(app, ["eval", "list-datasets"])
    assert r.exit_code == 0
    assert "agentrouter-gold" in r.output


def test_validate_dataset_by_name():
    r = runner.invoke(app, ["eval", "validate-dataset", "agentrouter-gold"])
    assert r.exit_code == 0
    assert "validated" in r.output


def test_validate_unknown_dataset_exits_3():
    r = runner.invoke(app, ["eval", "validate-dataset", "no-such-dataset-xyz"])
    assert r.exit_code == 3


def test_run_fast_json(tmp_path):
    r = runner.invoke(app, ["eval", "run", "--profile", "fast", "--json", "--no-artifacts"])
    assert r.exit_code == 0, r.output
    report = json.loads(r.output[r.output.index("{") :])
    assert report["n_cases"] >= 150
    assert "release_gates" in report


def test_run_all_exercises_frozen_holdout_and_reports_gate_consistently():
    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--all",
            "--json",
            "--no-artifacts",
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output[result.output.index("{") :])
    generalization = report["context_band_generalization"]
    assert generalization["current_holdout"]["n"] == 45
    accuracy = generalization["current_holdout"]["accuracy"]
    assert report["release_gates"]["context_band_accuracy>=0.90"] is (accuracy >= 0.90)
    assert report["release_ready"] is all(report["release_gates"].values())


def test_require_release_ready_returns_nonzero_for_failed_result(monkeypatch):
    failed = {
        "grade_over_100": 99.0,
        "grade_of_measured": 99.0,
        "release_ready": False,
        "n_cases": 1,
        "datasets": {},
        "release_gates": {"context_band_accuracy>=0.90": False},
        "classification": {},
    }
    monkeypatch.setattr(evaluation_cli.runner, "run", lambda **_kwargs: failed)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--all",
            "--json",
            "--no-artifacts",
            "--require-release-ready",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["release_ready"] is False


def test_require_release_ready_requires_complete_measurement():
    result = runner.invoke(
        app,
        ["eval", "run", "--json", "--no-artifacts", "--require-release-ready"],
    )

    assert result.exit_code == 2
    assert "requires --all" in result.output


def test_run_writes_artifacts(tmp_path):
    r = runner.invoke(app, ["eval", "run", "--profile", "fast", "--out-dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "result.json").exists()
    assert (tmp_path / "scorecard.json").exists()


def test_run_with_limit_is_deterministic():
    args = [
        "eval",
        "run",
        "--dataset",
        "agentrouter-gold",
        "--limit",
        "30",
        "--json",
        "--no-artifacts",
    ]
    a = runner.invoke(app, args)
    b = runner.invoke(app, args)
    assert a.exit_code == 0 and b.exit_code == 0
    ra = json.loads(a.output[a.output.index("{") :])
    rb = json.loads(b.output[b.output.index("{") :])
    assert ra["n_cases"] == rb["n_cases"] == 30
