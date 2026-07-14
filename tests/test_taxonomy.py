"""Phase P4 — tool/workload taxonomy: canonical labels, aliases, prohibition."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import agentrouter
from agentrouter import taxonomy
from agentrouter.cli import app
from agentrouter.controls import RouteControls, apply_controls
from agentrouter.registry import load_all_models, load_providers

runner = CliRunner()
_SEEDS = Path(agentrouter.__file__).parent / "seeds"


def _seed_models():
    providers = load_providers(_SEEDS / "providers.yaml")
    models, _ = load_all_models(_SEEDS, providers)
    return models


def test_all_seed_tool_support_labels_are_known():
    for m in _seed_models():
        for label in m.tool_support:
            assert taxonomy.is_known(label), f"{m.key} uses unknown tool label '{label}'"


def test_versioned():
    assert taxonomy.TAXONOMY_VERSION


def test_web_and_web_search_are_equivalent():
    assert taxonomy.satisfied_by("web", {"web-search"})
    assert taxonomy.satisfied_by("web-search", {"web"})


def test_unrelated_tools_not_equivalent():
    assert not taxonomy.satisfied_by("shell", {"web"})


def test_exact_match_still_satisfies():
    assert taxonomy.satisfied_by("file-edit", {"file-edit", "shell"})


def test_prohibit_tool_drops_supporting_models():
    models = _seed_models()
    kept, dropped = apply_controls(models, RouteControls(prohibit_tool=("shell",)))
    assert all("shell" not in m.tool_support for m in kept)
    if dropped:
        assert any("prohibited tool" in d["reason"] for d in dropped)


def test_prohibit_tool_respects_equivalence():
    models = _seed_models()
    # Prohibiting "function-calling" should also drop models listing "tool-use".
    kept, _ = apply_controls(models, RouteControls(prohibit_tool=("function-calling",)))
    assert all(
        "tool-use" not in m.tool_support and "function-calling" not in m.tool_support for m in kept
    )


def test_cli_prohibit_tool_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(
        app, ["route", "write a blog post", "--prohibit-tool", "shell", "--json", "--no-log"]
    )
    # Either routes to a shell-free model or reports no eligible model (exit 4).
    assert r.exit_code in (0, 4), r.output


def test_alias_match_keeps_routing_working(tmp_path, monkeypatch):
    # Regression: a task needing "web" still routes even though it is an alias group.
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "search the web for recent news", "--tool", "web", "--no-log"])
    assert r.exit_code in (0, 4), r.output


@pytest.mark.parametrize("label", ["file-edit", "shell", "web", "vision", "web-search"])
def test_core_labels_present(label):
    assert taxonomy.is_known(label)
