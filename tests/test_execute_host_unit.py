"""Mutation-hardening for cli._execute_via_host — the Phase-7 execution path.

Every branch, exit code, and operator-facing string is pinned by calling the
function directly against a seeded registry with a monkeypatched resolved route.
The execution-bypass guarantees (dry-run never runs; unavailable host refuses;
missing --yes refuses) are asserted explicitly.
"""

from __future__ import annotations

import sys

import pytest
import typer
from factories import make_target

from agentrouter import cli
from agentrouter.hosts import AVAILABLE, UNAVAILABLE, HostStatus, ResolvedRoute
from agentrouter.schema import ExecutionMode

EXIT_RUNTIME, EXIT_USAGE = 1, 2


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from typer.testing import CliRunner

    from agentrouter.cli import app

    CliRunner().invoke(app, ["init"])
    _, models = cli._load_registries()
    assert models, "seed registry must have models"
    return models


def _route(monkeypatch, target, status):
    statuses = [status] if status else []
    monkeypatch.setattr(
        cli.hosts,
        "resolve_execution_route",
        lambda model, include_unavailable=False: ResolvedRoute(target, status, statuses),
    )


def _call(rec_model, prompt="hi", *, yes=True, dry_run=False):
    with pytest.raises(typer.Exit) as ei:
        cli._execute_via_host({"model": rec_model}, {}, prompt, yes=yes, dry_run=dry_run)
    return ei.value.exit_code


def test_unknown_model_key_is_usage_error(seeded, capsys):
    code = _call("no/such-model")
    assert code == EXIT_USAGE
    assert "no longer in the registry" in capsys.readouterr().err


def test_no_execution_target_is_usage_error(seeded, monkeypatch, capsys):
    _route(monkeypatch, None, None)
    code = _call(seeded[0].key)
    assert code == EXIT_USAGE
    assert "No execution target" in capsys.readouterr().err


def test_dry_run_previews_and_never_executes(seeded, monkeypatch, capsys):
    tgt = make_target(host="claude-code", command_template=["claude", "-p", "{prompt}"])
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "'claude' found on PATH"))
    code = _call(seeded[0].key, dry_run=True, yes=True)
    out = capsys.readouterr().out
    assert code == 0
    assert "Dry run: nothing executed." in out
    assert "Run through: claude-code" in out
    assert "Availability: available" in out
    assert "Command:" in out  # command preview shown


def test_dry_run_wins_even_when_unavailable(seeded, monkeypatch):
    # --dry-run must short-circuit before the availability gate.
    tgt = make_target(host="claude-code", command_template=["claude", "{prompt}"])
    _route(monkeypatch, tgt, HostStatus("claude-code", UNAVAILABLE, "missing"))
    assert _call(seeded[0].key, dry_run=True) == 0


def test_manual_host_without_command_exits_zero(seeded, monkeypatch, capsys):
    tgt = make_target(host="manual", execution_mode=ExecutionMode.manual, command_template=None)
    st = HostStatus("manual", AVAILABLE, "manual execution is always available")
    _route(monkeypatch, tgt, st)
    code = _call(seeded[0].key)
    out = capsys.readouterr().out
    assert code == 0
    assert "no local command" in out
    assert "manual" in out


def test_unavailable_host_refuses_execution(seeded, monkeypatch, capsys):
    tgt = make_target(host="claude-code", command_template=["claude", "{prompt}"])
    _route(monkeypatch, tgt, HostStatus("claude-code", UNAVAILABLE, "not found"))
    code = _call(seeded[0].key, yes=True)
    err = capsys.readouterr().err
    assert code == EXIT_USAGE
    assert "Not enabled" in err
    assert "claude-code" in err


def test_available_but_missing_yes_refuses(seeded, monkeypatch, capsys):
    tgt = make_target(host="claude-code", command_template=["claude", "{prompt}"])
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "found"))
    code = _call(seeded[0].key, yes=False)
    assert code == EXIT_USAGE
    assert "--yes" in capsys.readouterr().out


def test_available_with_yes_runs_and_propagates_exit_code(seeded, monkeypatch):
    tgt = make_target(
        host="claude-code",
        command_template=[sys.executable, "-c", "import sys; sys.exit(7)", "{prompt}"],
    )
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "found"))
    assert _call(seeded[0].key, yes=True) == 7


def test_success_exit_code_zero(seeded, monkeypatch):
    tgt = make_target(
        host="claude-code",
        command_template=[sys.executable, "-c", "pass", "{prompt}"],
    )
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "found"))
    assert _call(seeded[0].key, yes=True) == 0


def test_prompt_placeholder_is_substituted(seeded, monkeypatch, capfd):
    tgt = make_target(
        host="claude-code",
        command_template=[sys.executable, "-c", "import sys; print(sys.argv[1])", "{prompt}"],
    )
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "found"))
    _call(seeded[0].key, prompt="INJECTED_MARKER", yes=True)
    assert "INJECTED_MARKER" in capfd.readouterr().out


def test_missing_binary_is_runtime_error(seeded, monkeypatch, capsys):
    tgt = make_target(
        host="claude-code",
        command_template=["definitely-not-a-real-binary-xyz", "{prompt}"],
        required_command="claude",
    )
    _route(monkeypatch, tgt, HostStatus("claude-code", AVAILABLE, "found"))
    code = _call(seeded[0].key, yes=True)
    err = capsys.readouterr().err
    assert code == EXIT_RUNTIME
    assert "command not found" in err
    assert "definitely-not-a-real-binary-xyz" in err
