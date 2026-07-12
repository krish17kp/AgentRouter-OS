"""CLI smoke tests — entrypoints work for a fresh user. No network, no keys."""

import subprocess
import sys

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    return tmp_path


def test_python_dash_m_help_runs():
    """`python -m agentrouter --help` — the no-install entrypoint."""
    r = subprocess.run(
        [sys.executable, "-m", "agentrouter", "--help"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert "route" in r.stdout and "registry" in r.stdout


def test_version_flag():
    from agentrouter.cli import app

    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "agentrouter-os" in r.output


def test_app_help_lists_all_commands():
    from agentrouter.cli import app

    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("init", "route", "explain", "feedback", "registry", "providers", "prompt"):
        assert cmd in r.output, f"missing command in --help: {cmd}"


def test_fresh_user_flow_init_list_route(home):
    """The README quick-start sequence, end to end."""
    from agentrouter.cli import app

    assert runner.invoke(app, ["init"]).exit_code == 0
    assert "MODEL_ID" in runner.invoke(app, ["registry", "list"]).output
    r = runner.invoke(app, ["route", "Polish the README for a Python CLI project"])
    assert r.exit_code == 0, r.output
    assert "How I read this task" in r.output and "writing" in r.output
