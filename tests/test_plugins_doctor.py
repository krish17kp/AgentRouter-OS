"""`agentrouter plugin doctor` diagnoses states and gives safe remedies (TASK-019).

The old doctor printed a status line and the install plan. That tells a user
*what* would happen, not *what is wrong* or *what to do*. These tests pin the
diagnosis for each state the installer can actually be in — including the two
that must never be confused, since one of them means "this file is yours".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentrouter import plugins
from agentrouter.cli import app

runner = CliRunner()


@pytest.fixture()
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.fixture()
def plugin():
    return plugins.get_plugin("claude-code")


def dest_of(root: Path, plugin) -> Path:
    return root / plugin.name / plugin.files[0].dest


def only_file_finding(plugin):
    return next(f for f in plugins.diagnose(plugin) if f["check"] == "file")


def test_a_clean_install_is_ok_with_no_remedy(root, plugin):
    plugins.install(plugin)
    finding = only_file_finding(plugin)
    assert finding["status"] == plugins.DIAG_OK
    assert finding["remedy"] is None, "a healthy state must not suggest an action"


def test_a_missing_install_says_how_to_install_it(root, plugin):
    finding = only_file_finding(plugin)
    assert finding["status"] == plugins.DIAG_ATTENTION
    assert "plugin install claude-code" in finding["remedy"]


def test_a_modified_file_is_never_described_as_only_ours(root, plugin):
    """`plan()` cannot distinguish 'you edited our file' from 'this was never
    ours', so the wording must be true of both — telling someone their own file
    is our modified copy would invite them to overwrite it."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("a file we never installed", encoding="utf-8")

    finding = only_file_finding(plugin)
    assert finding["status"] == plugins.DIAG_ATTENTION
    assert "your own" in finding["summary"]
    assert "--force" in finding["remedy"]
    assert "backed up" in finding["remedy"]


def test_an_identical_legacy_copy_offers_adoption(root, plugin):
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plugins._src_bytes(plugin.files[0].src))

    finding = only_file_finding(plugin)
    assert finding["status"] == plugins.DIAG_ATTENTION
    assert "--adopt-identical" in finding["remedy"]


def test_an_unsafe_destination_is_blocked_and_never_auto_fixed(root, plugin, tmp_path):
    """The remedy must not tell the user to delete something arbitrarily."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(tmp_path / "elsewhere" / "target")

    findings = plugins.diagnose(plugin)
    blocked = [f for f in findings if f["status"] == plugins.DIAG_BLOCKED]
    assert blocked, findings
    assert (
        "will not write through it" in blocked[0]["remedy"]
        or "resolve the path" in blocked[0]["remedy"]
    )


def test_an_unfinished_operation_is_reported(root, plugin):
    plugins.install(plugin)
    plugins._transaction_path(root / plugin.name, plugin).write_text(
        '{"stage": "interrupted"}', encoding="utf-8"
    )
    findings = plugins.diagnose(plugin)
    transaction = [f for f in findings if f["check"] == "transaction"]
    assert transaction, findings
    assert "did not finish" in transaction[0]["summary"]


def test_a_corrupt_ownership_record_is_blocked_and_says_why(root, plugin):
    plugins.install(plugin)
    plugins._state_path(root / plugin.name, plugin).write_text("{not json", encoding="utf-8")

    findings = plugins.diagnose(plugin)
    assert plugins.worst_status(findings) == plugins.DIAG_BLOCKED
    ownership = [f for f in findings if f["check"] == "ownership"]
    assert ownership
    assert "will not delete files it cannot prove it owns" in ownership[0]["remedy"]


def test_diagnose_all_never_raises_even_when_a_plugin_is_broken(root, plugin, monkeypatch):
    """A doctor that crashes is useless precisely when it is needed."""
    monkeypatch.setattr(
        plugins, "plan", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    findings = plugins.diagnose_all()
    assert findings
    assert all("status" in f for f in findings)


def test_the_cli_reports_findings_and_exits_by_severity(root, plugin):
    result = runner.invoke(app, ["plugin", "doctor"])
    assert result.exit_code == 2, result.output  # attention: not installed yet
    assert "not installed" in result.output
    assert "plugin install claude-code" in result.output

    plugins.install(plugins.get_plugin("claude-code"))
    plugins.install(plugins.get_plugin("codex"))
    healthy = runner.invoke(app, ["plugin", "doctor"])
    assert healthy.exit_code == 0, healthy.output


def test_the_cli_json_output_is_machine_readable(root, plugin):
    result = runner.invoke(app, ["plugin", "doctor", "--json"])
    payload = json.loads(result.output)
    assert payload["status"] in (
        plugins.DIAG_OK,
        plugins.DIAG_ATTENTION,
        plugins.DIAG_BLOCKED,
    )
    assert payload["findings"]


def test_plugin_doctor_never_prints_file_contents(root, plugin):
    """Output is meant to be pasteable into a support request."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    dest.write_text("SECRET-USER-CONTENT-abc123", encoding="utf-8")

    result = runner.invoke(app, ["plugin", "doctor"])
    assert "SECRET-USER-CONTENT" not in result.output


def test_the_unified_doctor_reports_plugin_state_without_duplicating_logic(root, plugin):
    """Two implementations of 'is this file ours?' would eventually disagree,
    and the wrong one would be the one that deletes something."""
    from agentrouter import diagnostics

    ids = {c.id for c in diagnostics.run_all(root / "home")}
    assert "plugins.state" in ids
