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


def test_run_rejects_invalid_source():
    r = runner.invoke(app, ["eval", "run", "--source", "bogus"])
    assert r.exit_code == 2
    assert "Invalid --source" in r.output


def test_run_reports_adapter_error(monkeypatch):
    def boom(**_kwargs):
        from agentrouter.evaluation.base import AdapterError

        raise AdapterError("dataset exploded")

    monkeypatch.setattr(evaluation_cli.runner, "run", boom)
    r = runner.invoke(app, ["eval", "run", "--no-artifacts"])
    assert r.exit_code == 3
    assert "dataset exploded" in r.output


def test_context_band_generalization_text():
    r = runner.invoke(app, ["eval", "context-band-generalization"])
    assert r.exit_code == 0, r.output
    assert "Holdout SHA-256" in r.output
    assert "Current accuracy" in r.output


def test_context_band_generalization_json():
    r = runner.invoke(app, ["eval", "context-band-generalization", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert "current_holdout" in payload and "holdout_sha256" in payload


def test_status_lists_every_dataset():
    r = runner.invoke(app, ["eval", "status"])
    assert r.exit_code == 0, r.output
    assert "agentrouter-gold" in r.output


def test_prepare_requires_dataset_or_all():
    r = runner.invoke(app, ["eval", "prepare"])
    assert r.exit_code == 2
    assert "--dataset" in r.output


def test_prepare_fixture_only_dataset_is_skipped_external_not_a_fallback():
    # agentrouter-gold has no real-source loader by design (project-internal
    # fixture); prepare must report that honestly rather than silently
    # succeeding as if a real download happened.
    r = runner.invoke(app, ["eval", "prepare", "--dataset", "agentrouter-gold"])
    assert r.exit_code == 1
    assert "SKIPPED_EXTERNAL" in r.output


def test_prepare_unknown_dataset_reports_unavailable_without_failing_all_run():
    r = runner.invoke(app, ["eval", "prepare", "--all"])
    assert r.exit_code == 0, r.output


def test_report_renders_markdown_from_result_json(tmp_path):
    run_result = runner.invoke(
        app, ["eval", "run", "--profile", "fast", "--out-dir", str(tmp_path)]
    )
    assert run_result.exit_code == 0, run_result.output
    result_json = tmp_path / "result.json"

    r = runner.invoke(app, ["eval", "report", str(result_json)])
    assert r.exit_code == 0, r.output
    assert r.output.strip()


def test_report_missing_file_exits_3(tmp_path):
    r = runner.invoke(app, ["eval", "report", str(tmp_path / "no-such-result.json")])
    assert r.exit_code == 3
    assert "Not found" in r.output


def test_compare_writes_artifacts_without_regression(tmp_path):
    baseline_dir = tmp_path / "baseline"
    current_dir = tmp_path / "current"
    for d in (baseline_dir, current_dir):
        r = runner.invoke(app, ["eval", "run", "--profile", "fast", "--out-dir", str(d)])
        assert r.exit_code == 0, r.output

    out_dir = tmp_path / "cmp"
    r = runner.invoke(
        app,
        [
            "eval",
            "compare",
            str(baseline_dir / "result.json"),
            str(current_dir / "result.json"),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "Grade delta" in r.output
    assert "Critical regression: NO" in r.output
    assert (out_dir / "comparison.md").exists()


def test_compare_missing_file_exits_3(tmp_path):
    r = runner.invoke(
        app,
        ["eval", "compare", str(tmp_path / "missing-baseline.json"), str(tmp_path / "also.json")],
    )
    assert r.exit_code == 3
    assert "Not found" in r.output


def test_compare_exits_nonzero_on_critical_regression(tmp_path, monkeypatch):
    baseline = {
        "grade_over_100": 90.0,
        "release_gates": {"gate-a": True},
        "dimensions": {"routing": {"score": 90.0}},
    }
    current = {
        "grade_over_100": 50.0,
        "release_gates": {"gate-a": False},
        "dimensions": {"routing": {"score": 10.0}},
    }
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    current_path.write_text(json.dumps(current), encoding="utf-8")

    r = runner.invoke(
        app,
        ["eval", "compare", str(baseline_path), str(current_path), "--out-dir", str(tmp_path)],
    )
    assert r.exit_code == 1
    assert "Critical regression: YES" in r.output
