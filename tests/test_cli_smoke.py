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
        [sys.executable, "-m", "agentrouter", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",  # Rich emits UTF-8 box-drawing; don't decode with the Windows locale
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


def test_route_verify_live_is_opt_in_and_never_crashes(home):
    """No live usage adapter is registered in production, so --verify-live is a
    documented no-op (source of truth for the mechanism: tests/test_usage.py)."""
    from agentrouter.cli import app

    assert runner.invoke(app, ["init"]).exit_code == 0
    r = runner.invoke(
        app, ["route", "Polish the README for a Python CLI project", "--verify-live", "--json"]
    )
    assert r.exit_code == 0, r.output
    import json

    payload = json.loads(r.output)
    assert payload["usage_check"]["state"] == "unsupported"


def test_route_without_verify_live_has_no_usage_check_field(home):
    from agentrouter.cli import app

    assert runner.invoke(app, ["init"]).exit_code == 0
    r = runner.invoke(app, ["route", "Polish the README for a Python CLI project", "--json"])
    assert r.exit_code == 0, r.output
    import json

    payload = json.loads(r.output)
    assert "usage_check" not in payload


def test_init_force_backs_up_hand_edited_catalog(home):
    """--force must not silently destroy a user's edited catalog (M1)."""
    from agentrouter.cli import app

    assert runner.invoke(app, ["init"]).exit_code == 0
    models = home / "registry" / "models.yaml"
    models.write_text("# my hand edits\n", encoding="utf-8")

    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    backup = models.with_suffix(".yaml.bak")
    assert backup.read_text(encoding="utf-8") == "# my hand edits\n"
    assert models.read_text(encoding="utf-8") != "# my hand edits\n"  # reseeded
