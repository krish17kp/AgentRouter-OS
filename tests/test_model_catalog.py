"""Phase 11 — real model catalog, vendor/host separation, two-stage routing."""

import json

from typer.testing import CliRunner

from agentrouter import hosts
from agentrouter.cli import app

runner = CliRunner()

_PLACEHOLDERS = {
    "frontier-coding-model",
    "fast-coding-model",
    "general-purpose-model",
    "ide-coding-model",
    "cheap-fast-model",
    "strong-coding-model",
    "mid-tier-coding-model",
    "long-context-writer-model",
    "frontier-reasoning-model",
    "legacy-general-model",
}


def _seed_models():
    from importlib import resources

    import yaml

    text = (resources.files("agentrouter.seeds") / "models.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["models"]


def test_no_placeholder_ids_in_production_seed():
    ids = {m["model_id"] for m in _seed_models()}
    assert ids.isdisjoint(_PLACEHOLDERS), f"placeholder seeds present: {ids & _PLACEHOLDERS}"


def test_real_anthropic_and_openai_models_present():
    ids = {m["model_id"] for m in _seed_models()}
    assert {"claude-sonnet-5", "claude-opus-4-8", "claude-fable-5"} <= ids
    assert {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"} <= ids


def test_every_seed_has_vendor_and_execution_targets():
    for m in _seed_models():
        assert m.get("vendor"), m["model_id"]
        assert m.get("execution_targets"), m["model_id"]


def test_vendor_is_distinct_from_execution_host():
    for m in _seed_models():
        vendor = m["vendor"]
        hosts_used = {t["host"] for t in m["execution_targets"]}
        # a host like claude-code / codex-cli / *-api is never the vendor name itself
        assert vendor not in {"claude-code", "codex-cli", "cursor"}
        if vendor != "manual":
            assert hosts_used - {f"{vendor}-api"}  # has at least one non-trivial host


def test_route_recommends_real_model_with_host(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "build a rag system that parses PDFs", "--json", "--no-log"])
    assert r.exit_code == 0, r.output
    d = json.loads(r.output)
    assert d["recommendation"]["model_id"] not in _PLACEHOLDERS
    er = d["execution_route"]
    assert er is not None
    assert er["vendor"] in {"anthropic", "openai", "google", "manual"}
    assert er["host"] is not None
    assert er["availability"] in {"available", "unavailable", "unknown"}


def test_unknown_availability_never_promoted_to_available():
    st = hosts.detect_host("some-unrecognized-host")
    assert st.availability == hosts.UNKNOWN


def test_api_host_unavailable_without_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    st = hosts.detect_host("anthropic-api")
    assert st.availability == hosts.UNAVAILABLE


def test_command_preview_redacts_prompt():
    from agentrouter.schema import ExecutionTarget

    t = ExecutionTarget(
        host="claude-code",
        host_model_id="claude-sonnet-5",
        command_template=["claude", "-p", "--model", "claude-sonnet-5", "{prompt}"],
        required_command="claude",
    )
    preview = hosts.command_preview(t, redact=True)
    assert "{prompt}" not in preview
    assert "redacted" in preview


def test_hosts_doctor_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["hosts", "doctor"])
    # exit 0 if any host available, else 1 — both are valid; output lists hosts
    assert "manual" in r.output


def test_models_show_reports_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["models", "show", "anthropic/claude-sonnet-5"])
    assert r.exit_code == 0, r.output
    assert "source=curated" in r.output
    assert "claude-code" in r.output


def test_backward_compat_json_keeps_recommendation_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "write a haiku", "--json", "--no-log"])
    d = json.loads(r.output)
    # legacy keys still present (no abrupt contract break)
    for key in ("recommendation", "fallback", "classification", "scores", "prompt"):
        assert key in d
    assert {"model", "provider", "model_id", "score"} <= set(d["recommendation"])
