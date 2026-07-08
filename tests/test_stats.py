"""M7-lite — local telemetry aggregates and the policy pricing cap."""

import json

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_stats_requires_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "nothing"))
    from agentrouter.cli import app

    r = runner.invoke(app, ["stats"])
    assert r.exit_code == 2


def test_stats_aggregates(home):
    from agentrouter.cli import app

    runner.invoke(app, ["route", "write a short haiku"])
    r2 = runner.invoke(app, ["route", "rotate the production auth credentials", "--json"])
    did = json.loads(r2.output)["decision_id"]
    runner.invoke(app, ["feedback", did, "--rating", "5"])

    r = runner.invoke(app, ["stats", "--json"])
    assert r.exit_code == 0, r.output
    agg = json.loads(r.output)
    assert agg["decisions"] == 2
    assert agg["by_risk"] == {"low": 1, "high": 1}
    assert agg["feedback"]["count"] == 1
    assert agg["feedback"]["acceptance_rate"] == 1.0
    assert sum(agg["by_pricing_tier"].values()) == 2

    human = runner.invoke(app, ["stats"])
    assert "Decisions logged: 2" in human.output


def test_policy_max_pricing_tier_caps_routing(home):
    from agentrouter.cli import app

    cfg = home / "config.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8") + "\npolicy:\n  max_pricing_tier: low\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["route", "refactor the logging module", "--json"])
    assert r.exit_code == 0, r.output
    assert "policy: excluded" in r.output  # CliRunner merges the stderr note into output
    payload = json.loads(r.output[r.output.index("{") :])
    tiers = {"free", "low"}
    from agentrouter.registry import load_all_models, load_providers

    reg_dir = home / "registry"
    models = {
        m.key: m for m in load_all_models(reg_dir, load_providers(reg_dir / "providers.yaml"))[0]
    }
    for row in payload["scores"]:
        assert models[row["model"]].pricing_tier.value in tiers


def test_policy_invalid_tier_fails_loud(home):
    from agentrouter.cli import app

    cfg = home / "config.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8") + "\npolicy:\n  max_pricing_tier: platinum\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["route", "write a haiku"])
    assert r.exit_code == 3
    assert "platinum" in r.output
