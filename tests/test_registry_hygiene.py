"""M3 — staleness warnings and curated ability overrides."""

from datetime import date, timedelta

import pytest
import yaml
from typer.testing import CliRunner

from agentrouter.refresh import write_generated_registry
from agentrouter.registry import (
    STALE_AFTER_DAYS,
    RegistryError,
    load_all_models,
    load_providers,
)
from agentrouter.schema import Ability, LatencyTier, ModelEntry, PricingTier

runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


def _entry(**overrides) -> ModelEntry:
    base = dict(
        provider="openrouter",
        model_id="test/stale-model",
        context_window=64000,
        max_output_tokens=8000,
        pricing_tier=PricingTier.low,
        latency_tier=LatencyTier.medium,
        ability=Ability(coding=5, reasoning=5, writing=5),
        tool_support=[],
        vision_support=False,
        deprecation_status="active",
        source="refresh",
        last_updated=date.today(),
    )
    base.update(overrides)
    return ModelEntry(**base)


def _load(home):
    reg_dir = home / "registry"
    providers = load_providers(reg_dir / "providers.yaml")
    return load_all_models(reg_dir, providers)


# --- staleness ------------------------------------------------------------------


def test_stale_entry_warns(home):
    old = date.today() - timedelta(days=STALE_AFTER_DAYS + 1)
    write_generated_registry(home / "registry", "openrouter", [_entry(last_updated=old)])
    _, warnings = _load(home)
    assert any("older than" in w and "stale-model" in w for w in warnings)


def test_fresh_entries_do_not_warn(home):
    _, warnings = _load(home)
    assert not any("older than" in w for w in warnings)


# --- ability overrides ------------------------------------------------------------


def test_override_applies_partial_scores(home):
    write_generated_registry(home / "registry", "openrouter", [_entry()])
    (home / "registry" / "ability_overrides.yaml").write_text(
        yaml.safe_dump({"overrides": {"openrouter/test/stale-model": {"coding": 9}}}),
        encoding="utf-8",
    )
    models, warnings = _load(home)
    m = next(m for m in models if m.model_id == "test/stale-model")
    assert m.ability.coding == 9
    assert m.ability.reasoning == 5  # untouched dimensions keep their values
    assert not any("does not match" in w for w in warnings)


def test_override_unknown_key_warns_not_fails(home):
    (home / "registry" / "ability_overrides.yaml").write_text(
        yaml.safe_dump({"overrides": {"openrouter/ghost": {"coding": 9}}}), encoding="utf-8"
    )
    _, warnings = _load(home)
    assert any("ghost" in w and "does not match" in w for w in warnings)


def test_override_invalid_score_fails_loud(home):
    (home / "registry" / "ability_overrides.yaml").write_text(
        yaml.safe_dump({"overrides": {"claude-code/frontier-coding-model": {"coding": 99}}}),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="frontier-coding-model"):
        _load(home)


def test_override_survives_refresh_overwrite(home):
    """The whole point: curation lives outside the generated file refresh rewrites."""
    reg_dir = home / "registry"
    (reg_dir / "ability_overrides.yaml").write_text(
        yaml.safe_dump({"overrides": {"openrouter/test/stale-model": {"coding": 10}}}),
        encoding="utf-8",
    )
    for _ in range(2):  # refresh overwrites the generated file; override still applies
        write_generated_registry(reg_dir, "openrouter", [_entry()])
        models, _ = _load(home)
        m = next(m for m in models if m.model_id == "test/stale-model")
        assert m.ability.coding == 10
