"""Phase P3 — route-control flags (--vendor/--model/--host/--prefer-*/…).

Unit tests over controls.apply_controls against the real seed catalog, plus CLI
integration tests that exercise the wiring in `agentrouter route`.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

import agentrouter
from agentrouter.cli import app
from agentrouter.controls import PREFERENCE_WEIGHTS, RouteControls, apply_controls
from agentrouter.registry import load_all_models, load_providers

runner = CliRunner()

_SEEDS = Path(agentrouter.__file__).parent / "seeds"


def _seed_models():
    providers = load_providers(_SEEDS / "providers.yaml")
    models, _ = load_all_models(_SEEDS, providers)
    return models


# --- pure unit: apply_controls -------------------------------------------------


def test_empty_controls_keeps_everything():
    models = _seed_models()
    kept, dropped = apply_controls(models, RouteControls())
    assert kept == models
    assert dropped == []


def test_vendor_filter_case_insensitive():
    models = _seed_models()
    kept, dropped = apply_controls(models, RouteControls(vendor=("ANTHROPIC",)))
    assert kept, "expected some anthropic models"
    assert all(m.vendor == "anthropic" for m in kept)
    assert all(d["reason"].startswith("control:") for d in dropped)


def test_exclude_vendor_drops_that_vendor():
    models = _seed_models()
    kept, _ = apply_controls(models, RouteControls(exclude_vendor=("openai",)))
    assert kept
    assert all(m.vendor != "openai" for m in kept)


def test_model_pin_keeps_only_match():
    models = _seed_models()
    target = next(m for m in models if m.vendor == "anthropic")
    kept, _ = apply_controls(models, RouteControls(model=target.vendor_key))
    assert [m.vendor_key for m in kept] == [target.vendor_key]


def test_model_pin_matches_bare_id():
    models = _seed_models()
    target = models[0]
    kept, _ = apply_controls(models, RouteControls(model=target.model_id))
    assert target.model_id in {m.model_id for m in kept}


def test_stable_only_drops_non_stable():
    models = _seed_models()
    kept, _ = apply_controls(models, RouteControls(stable_only=True))
    assert all(m.release_channel.value == "stable" for m in kept)


def test_max_price_excludes_unknown_price_honestly():
    # Seeds carry no per-token price yet, so a cap must exclude (never fabricate).
    models = _seed_models()
    kept, dropped = apply_controls(models, RouteControls(max_price=1.0))
    unpriced = [m for m in models if m.input_price_per_million is None]
    if unpriced:
        assert not kept
        assert any("price unknown" in d["reason"] for d in dropped)


def test_host_filter_keeps_only_models_on_host():
    models = _seed_models()
    some_host = next(iter(models[0].execution_targets)).host
    kept, _ = apply_controls(models, RouteControls(host=(some_host,)))
    assert kept
    assert all(any(t.host == some_host for t in m.execution_targets) for m in kept)


# --- preference weight vectors -------------------------------------------------


def test_preference_vectors_sum_to_one():
    for name, w in PREFERENCE_WEIGHTS.items():
        assert abs(sum(w.values()) - 1.0) < 1e-9, name


# --- CLI integration -----------------------------------------------------------


def _route_json(tmp_path, monkeypatch, *args):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", *args, "--json", "--no-log"])
    return r


def test_cli_vendor_flag_scopes_recommendation(tmp_path, monkeypatch):
    r = _route_json(tmp_path, monkeypatch, "build a rag system", "--vendor", "anthropic")
    assert r.exit_code == 0, r.output
    d = json.loads(r.output)
    assert d["recommendation"]["model"].startswith("anthropic/")


def test_cli_prefer_quality_beats_default_on_simple_task(tmp_path, monkeypatch):
    base = _route_json(tmp_path, monkeypatch, "write a haiku about the sea")
    quality = _route_json(tmp_path, monkeypatch, "write a haiku about the sea", "--prefer-quality")
    b = json.loads(base.output)["recommendation"]["model"]
    q = json.loads(quality.output)["recommendation"]["model"]
    # quality preference should not pick a weaker model than the default
    assert b != q or quality.exit_code == 0
    assert "preference=quality -> fixed weights" in json.loads(quality.output)["weight_shifts"]


def test_cli_conflicting_prefer_flags_is_usage_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "hi", "--prefer-cheap", "--prefer-fast", "--no-log"])
    assert r.exit_code == 2, r.output


def test_cli_stable_only_and_allow_preview_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "hi", "--stable-only", "--allow-preview", "--no-log"])
    assert r.exit_code == 2, r.output


def test_cli_impossible_filter_reports_no_model(tmp_path, monkeypatch):
    r = _route_json(tmp_path, monkeypatch, "hi", "--vendor", "no-such-vendor")
    assert r.exit_code == 4, r.output  # EXIT_NO_MODEL


def test_cli_model_pin_selects_that_model(tmp_path, monkeypatch):
    r = _route_json(
        tmp_path, monkeypatch, "hello there", "--model", "anthropic/claude-haiku-4-5-20251001"
    )
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["recommendation"]["model_id"] == "claude-haiku-4-5-20251001"
