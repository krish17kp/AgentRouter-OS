"""Tests for the `agentrouter eval` CLI sub-app."""

import json

from typer.testing import CliRunner

from agentrouter.cli import app

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
