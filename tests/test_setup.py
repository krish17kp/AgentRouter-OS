"""Phase P9 — `agentrouter setup` onboarding wizard (non-interactive, idempotent)."""

import yaml
from typer.testing import CliRunner

from agentrouter.cli import app
from agentrouter.controls import PREFERENCE_WEIGHTS

runner = CliRunner()


def test_setup_creates_home_and_runs_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    r = runner.invoke(app, ["setup", "--preference", "cheap"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / "registry" / "models.yaml").exists()
    assert "Sample route" in r.output


def test_setup_writes_preference_weights(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["setup", "--preference", "quality"])
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["weights"] == PREFERENCE_WEIGHTS["quality"]


def test_setup_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    first = runner.invoke(app, ["setup"])
    second = runner.invoke(app, ["setup"])
    assert first.exit_code == 0 and second.exit_code == 0
    assert "exists, skipped" in second.output  # init reported existing files


def test_setup_rejects_unknown_preference(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    r = runner.invoke(app, ["setup", "--preference", "nope"])
    assert r.exit_code == 2, r.output


def test_setup_never_prints_secret_values(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-should-not-appear")
    r = runner.invoke(app, ["setup"])
    assert "sk-secret-value-should-not-appear" not in r.output
