"""Phase P8 — plugin/skill installer (reversible, idempotent, safe)."""

import pytest
from typer.testing import CliRunner

from agentrouter import plugins
from agentrouter.cli import app

runner = CliRunner()


@pytest.fixture
def plug_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    return tmp_path


def _dest(p, tmp_path):
    return tmp_path / p.name / p.files[0].dest


def test_install_creates_file(plug_root):
    p = plugins.get_plugin("claude-code")
    results = plugins.install(p)
    dest = _dest(p, plug_root)
    assert dest.exists()
    assert plugins.status(p) == "installed"
    assert results[0]["result"] == "created"


def test_install_is_idempotent(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    second = plugins.install(p)
    assert "skipped" in second[0]["result"]


def test_install_refuses_to_clobber_without_force(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("USER CONTENT", encoding="utf-8")
    with pytest.raises(plugins.PluginError):
        plugins.install(p)
    assert dest.read_text(encoding="utf-8") == "USER CONTENT"  # untouched


def test_force_backs_up_then_uninstall_restores(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("USER CONTENT", encoding="utf-8")
    plugins.install(p, force=True)
    assert dest.read_text(encoding="utf-8") != "USER CONTENT"  # replaced
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    assert backup.exists()
    plugins.uninstall(p)
    assert dest.read_text(encoding="utf-8") == "USER CONTENT"  # restored
    assert not backup.exists()


def test_uninstall_removes_created_file(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    plugins.uninstall(p)
    assert not _dest(p, plug_root).exists()
    assert plugins.status(p) == "not-installed"


def test_plan_changes_nothing(plug_root):
    p = plugins.get_plugin("codex")
    plan = plugins.plan(p)
    assert plan[0]["action"] == "create"
    assert not _dest(p, plug_root).exists()  # plan is read-only


def test_unknown_plugin_raises():
    with pytest.raises(plugins.PluginError):
        plugins.get_plugin("does-not-exist")


# --- CLI wiring ---------------------------------------------------------------


def test_cli_install_and_uninstall_roundtrip(plug_root):
    r = runner.invoke(app, ["plugin", "install", "claude-code"])
    assert r.exit_code == 0, r.output
    assert "created" in r.output
    r2 = runner.invoke(app, ["plugin", "uninstall", "claude-code"])
    assert r2.exit_code == 0, r2.output
    assert "removed" in r2.output


def test_cli_unknown_plugin_is_usage_error(plug_root):
    r = runner.invoke(app, ["plugin", "install", "nope"])
    assert r.exit_code == 2, r.output
