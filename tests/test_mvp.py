"""MVP acceptance tests — mirrors the M1 validation checklist in MILESTONES.md."""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agentrouter.classifier import classify
from agentrouter.engine import eligibility, route
from agentrouter.registry import RegistryError, load_models, load_providers
from agentrouter.safety import gates_for
from agentrouter.schema import Level, TaskType

runner = CliRunner()

SEEDS = Path(__file__).resolve().parents[1] / "agentrouter" / "seeds"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolated AGENTROUTER_HOME, initialized via the real init command."""
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


@pytest.fixture()
def registries():
    providers = load_providers(SEEDS / "providers.yaml")
    models, warnings = load_models(SEEDS / "models.yaml", providers)
    assert warnings == []
    return providers, models


# --- FR-1: classification of the three sample tasks --------------------------


def test_classify_trivial_script():
    c = classify("write a bash one-liner to count lines in a file")
    assert c.task_type is TaskType.coding
    assert c.complexity is Level.low
    assert c.risk is Level.low
    assert c.approval_level.value == "auto"


def test_classify_high_risk_refactor():
    c = classify("Refactor our auth module to use JWT rotation and add tests")
    assert c.task_type is TaskType.coding
    assert c.complexity is Level.high
    assert c.risk is Level.high
    assert c.output_type.value == "code+tests"
    assert "file-edit" in c.tool_needs and "shell" in c.tool_needs
    assert c.approval_level.value == "human-approval-required"


def test_classify_long_summary():
    c = classify("Summarize this 300k-token filing into 10 bullets")
    assert c.task_type is TaskType.summarization
    assert c.context_tokens == 300000
    assert c.context_band.value == "large"
    assert c.risk is Level.low  # regression: "300k-token" must not trip the risk keyword list


# --- FR-2: registry validation fails loudly ----------------------------------


def test_malformed_model_entry_names_field(tmp_path):
    providers = load_providers(SEEDS / "providers.yaml")
    bad = {
        "models": [
            {
                "provider": "openai",
                "model_id": "x",
                "max_output_tokens": 100,
                "pricing_tier": "low",
                "latency_tier": "fast",
                "ability": {"coding": 5, "reasoning": 5, "writing": 5},
                "tool_support": [],
                "vision_support": False,
                "deprecation_status": "active",
            }
        ]
    }  # missing context_window
    p = tmp_path / "models.yaml"
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(RegistryError, match="context_window"):
        load_models(p, providers)


def test_unknown_field_rejected(tmp_path):
    providers = load_providers(SEEDS / "providers.yaml")
    data = yaml.safe_load((SEEDS / "models.yaml").read_text(encoding="utf-8"))
    data["models"][0]["surprise_field"] = 1
    p = tmp_path / "models.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(RegistryError):
        load_models(p, providers)


# --- FR-5: context-size hard filter ------------------------------------------


def test_context_filter_excludes_small_models(registries):
    _, models = registries
    c = classify("Summarize this 300k-token filing into 10 bullets")
    eligible, excluded = eligibility(models, c)
    for m in eligible:
        assert m.context_window >= 300000
    assert any("context" in e["reason"] for e in excluded)


# --- FR-6/FR-8: risk gates ----------------------------------------------------


def test_high_risk_gates(registries):
    c = classify("Refactor our auth module to use JWT rotation and add tests")
    g = gates_for(c)
    assert g["approval_level"] == "human-approval-required"
    assert g["auto_execute_allowed"] is False
    assert len(g["checklist"]) >= 3


# --- FR-3/FR-4: scoring, recommendation + fallback ----------------------------


def test_route_returns_recommendation_and_fallback(registries):
    _, models = registries
    c = classify("Refactor our auth module to use JWT rotation and add tests")
    result = route(models, c)
    assert result["recommendation"] is not None
    assert result["fallback"] is not None
    assert result["recommendation"]["model"] != result["fallback"]["model"]
    # high-risk coding: capability-weighted -> a strong coding model wins
    assert result["scores"][0]["terms"]["cap"] >= 0.8


def test_cheap_task_prefers_cheap_tier(registries):
    _, models = registries
    c = classify("write a bash one-liner to count lines in a file")
    result = route(models, c)
    top = result["recommendation"]
    entry = next(m for m in models if m.key == top["model"])
    assert entry.pricing_tier.value in ("free", "low", "medium")


def test_vision_task_requires_vision(registries):
    _, models = registries
    c = classify("Describe what's wrong in this UI screenshot")
    assert "vision" in c.tool_needs
    eligible, _ = eligibility(models, c)
    assert eligible and all(m.vision_support for m in eligible)


# --- FR-9/FR-11: end-to-end CLI, log + explain reproduces ----------------------


def test_route_and_explain_end_to_end(home):
    from agentrouter.cli import app

    r = runner.invoke(
        app, ["route", "Refactor our auth module to use JWT rotation and add tests", "--json"]
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    did = payload["decision_id"]
    assert did and payload["recommendation"]

    e = runner.invoke(app, ["explain", did, "--json"])
    assert e.exit_code == 0, e.output
    stored = json.loads(e.output)
    assert stored["classification"] == payload["classification"]
    assert [s["model"] for s in stored["scores"]] == [s["model"] for s in payload["scores"]]


def test_registry_list_and_prompt_generate(home, tmp_path):
    from agentrouter.cli import app

    r = runner.invoke(app, ["registry", "list", "--active-only"])
    assert r.exit_code == 0 and "MODEL_ID" in r.output

    out = tmp_path / "prompt.md"
    p = runner.invoke(app, ["prompt", "generate", "write a haiku about routers", "--out", str(out)])
    assert p.exit_code == 0, p.output
    assert out.exists() and "# Execution Prompt" in out.read_text(encoding="utf-8")


def test_no_eligible_model_exit_code(home):
    from agentrouter.cli import app

    # demand an impossible tool so nothing qualifies
    r = runner.invoke(app, ["route", "do something", "--tool", "quantum-teleport"])
    assert r.exit_code == 4


# --- classifier regressions: docs must not become coding ----------------------

DOC_TASKS = [
    "Polish the README for a Python CLI project",
    "Rewrite the README and create a polished project overview",
    "Create PRD and BRD for this repo",
    "Generate architecture documentation for a backend service",
    "Write a roadmap and milestones document",
]


@pytest.mark.parametrize("task", DOC_TASKS)
def test_doc_tasks_classify_as_writing(task):
    c = classify(task)
    assert c.task_type is TaskType.writing, f"{task!r} -> {c.task_type}"
    assert c.output_type.value in ("text", "plan")  # never code
    assert "file-edit" not in c.tool_needs and "shell" not in c.tool_needs


def test_true_coding_task_still_coding():
    c = classify("Build a Python Typer CLI command")
    assert c.task_type is TaskType.coding
    assert c.output_type.value in ("code", "code+tests")


def test_high_risk_auth_migration_still_gated():
    c = classify("Refactor authentication routes and migrate JWT token handling in production")
    assert c.task_type is TaskType.coding
    assert c.risk is Level.high
    assert c.approval_level.value == "human-approval-required"
    g = gates_for(c)
    assert g["auto_execute_allowed"] is False


def test_summarize_repo_architecture_report(registries):
    _, models = registries
    c = classify("Summarize a 300k-token repository and generate an architecture report")
    assert c.task_type is TaskType.summarization
    assert c.context_tokens == 300000
    assert c.context_band.value == "large"
    result = route(models, c)
    rec = next(m for m in models if m.key == result["recommendation"]["model"])
    assert rec.context_window >= 300000


def test_docstring_task_is_still_coding():
    c = classify("Add docstrings to the functions in utils.py")
    assert c.task_type is TaskType.coding


# --- error-path UX -------------------------------------------------------------


def test_route_before_init_gives_registry_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "empty"))
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", "anything"])
    assert r.exit_code == 3
    assert "agentrouter init" in r.output


def test_explain_unknown_id_suggests_recent(home):
    from agentrouter.cli import app

    runner.invoke(app, ["route", "write a haiku", "--no-log"])  # no decision saved
    runner.invoke(app, ["route", "write a haiku"])  # d_00001 saved
    r = runner.invoke(app, ["explain", "d_99999"])
    assert r.exit_code == 2
    assert "d_00001" in r.output


def test_explain_without_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "nodb"))
    from agentrouter.cli import app

    r = runner.invoke(app, ["explain", "d_00001"])
    assert r.exit_code == 2
    assert "No decision log" in r.output


def test_route_json_contains_reason_and_stable_keys(home):
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", "Polish the README for a Python CLI project", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    for key in (
        "decision_id",
        "task",
        "classification",
        "scores",
        "recommendation",
        "fallback",
        "gates",
        "prompt",
        "reason",
    ):
        assert key in payload, f"missing key: {key}"
    assert payload["classification"]["task_type"] == "writing"


def test_invalid_config_yaml_errors_clearly(home):
    (home / "config.yaml").write_text("weights: [not: a: mapping", encoding="utf-8")
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", "write a haiku"])
    assert r.exit_code == 3
    assert "Config error" in r.output
