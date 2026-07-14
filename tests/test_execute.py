"""M6 — gated execution: opt-in per provider, high risk provably blocked."""

import json
import sys

import pytest
import yaml
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


def _route(task):
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", task, "--json"])
    assert r.exit_code == 0, r.output
    return json.loads(r.output)


def _enable_execution(home, provider_id, argv):
    path = home / "registry" / "providers.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for p in data["providers"]:
        if p["id"] == provider_id:
            p["supports_execution"] = True
            p["exec_command"] = argv
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


LOW_RISK_TASK = "write a short haiku about routers"
HIGH_RISK_TASK = "rotate the production auth credentials and deploy"


def test_high_risk_is_provably_blocked(home):
    from agentrouter.cli import app

    payload = _route(HIGH_RISK_TASK)
    assert payload["classification"]["risk"] == "high"
    # enable execution for every provider — the gate must still block
    for pid in ["claude-code", "openai", "openrouter", "cursor", "cli-agent", "manual"]:
        _enable_execution(home, pid, [sys.executable, "-c", "print('MUST NOT RUN')"])
    r = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert r.exit_code == 2
    assert "blocked" in r.output.lower()
    assert "MUST NOT RUN" not in r.output


def test_execute_dry_run_previews_host_command_without_running(home):
    """Phase 7: without legacy provider opt-in, execution resolves to the model's
    host. --dry-run previews the exact command and runs nothing (hermetic)."""
    from agentrouter.cli import app

    payload = _route(LOW_RISK_TASK)
    r = runner.invoke(app, ["execute", payload["decision_id"], "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Dry run" in r.output
    assert "Run through:" in r.output  # a real host was resolved, not a placeholder


def test_execute_via_host_refused_when_host_unavailable(home, monkeypatch):
    """Real execution is refused (exit 2) when no host is available — no fallback."""
    from agentrouter import hosts
    from agentrouter.cli import app

    monkeypatch.setattr(
        hosts,
        "detect_host",
        lambda host, required_command=None: hosts.HostStatus(
            host, hosts.UNAVAILABLE, "test: forced unavailable"
        ),
    )
    payload = _route(LOW_RISK_TASK)
    r = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert r.exit_code == 2
    assert "not enabled" in r.output.lower() or "unavailable" in r.output.lower()


def test_execute_requires_yes(home):
    from agentrouter.cli import app

    payload = _route(LOW_RISK_TASK)
    provider = payload["recommendation"]["provider"]
    _enable_execution(home, provider, [sys.executable, "-c", "print('ran')"])
    r = runner.invoke(app, ["execute", payload["decision_id"]])
    assert r.exit_code == 2
    assert "--yes" in r.output


def test_low_risk_executes_end_to_end(home, capfd):
    from agentrouter.cli import app

    payload = _route(LOW_RISK_TASK)
    assert payload["classification"]["risk"] == "low"
    provider = payload["recommendation"]["provider"]
    _enable_execution(home, provider, [sys.executable, "-c", "print('EXECUTED OK')"])
    r = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert r.exit_code == 0, r.output
    assert "EXECUTED OK" in capfd.readouterr().out  # subprocess output, not CliRunner's


def test_execute_propagates_subprocess_exit_code(home):
    from agentrouter.cli import app

    payload = _route(LOW_RISK_TASK)
    provider = payload["recommendation"]["provider"]
    _enable_execution(home, provider, [sys.executable, "-c", "import sys; sys.exit(7)"])
    r = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert r.exit_code == 7


def test_execute_unknown_id_exit2(home):
    from agentrouter.cli import app

    r = runner.invoke(app, ["execute", "d_99999", "--yes"])
    assert r.exit_code == 2
