"""Python/Rust `route --json` compatibility check for the R4 milestone.

Replicates `agentrouter/cli.py`'s `route()` command body using the same
library functions it calls (classify, engine.route, learned_weights,
gates_for, generate_prompt, hosts.execution_route_block) rather than the
Typer-wrapped command itself, mirroring how `test_routing_rust_compat.py`
calls `engine.route()` directly. Diffs that payload against the Rust
`agentrouter-cli` port (via the `cli_route_cli` bin) for the same seeded
registries and task.

Scope: default path only — no config.yaml, no preference flag, no
`--verify-live`. Skips (does not fail) when `cargo` isn't on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from agentrouter import hosts, store
from agentrouter.classifier import classify
from agentrouter.cli import app
from agentrouter.engine import BASE_WEIGHTS
from agentrouter.engine import route as engine_route
from agentrouter.learning import learned_weights
from agentrouter.prompts import generate_prompt
from agentrouter.registry import load_all_models, load_providers
from agentrouter.safety import gates_for

RUST_CRATE_DIR = "rust/agentrouter-cli"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")

TASKS = [
    "write a function",
    "Refactor auth to use JWT rotation and add tests",
    "summarize this document",
    "delete the production database",
]


@pytest.fixture
def seeded_home(tmp_path):
    home = tmp_path / "home"
    reg_dir = home / "registry"
    reg_dir.mkdir(parents=True)
    import agentrouter

    seeds = agentrouter.__path__[0] + "/seeds"
    shutil.copy(f"{seeds}/providers.yaml", reg_dir / "providers.yaml")
    shutil.copy(f"{seeds}/models.yaml", reg_dir / "models.yaml")
    store.connect(home).close()  # creates agentrouter.db so both sides see an empty feedback table
    return home


def _python_route_payload(home, task: str) -> dict:
    providers = load_providers(home / "registry" / "providers.yaml")
    models, _warnings = load_all_models(home / "registry", providers)
    cls = classify(task)
    conn = store.connect(home)
    weights, note = learned_weights(conn, BASE_WEIGHTS)
    result = engine_route(models, cls, weights)
    if note:
        result["weight_shifts"].append(note)
    models_by_key = {m.key: m for m in models}
    rec = result["recommendation"]
    target = rec["model"] if rec else (result["manual_suggestion"] or "manual/human-operator")
    gates = gates_for(cls)
    prompt = generate_prompt(task, target, cls, gates["checklist"])
    reason = None
    if rec:
        from agentrouter.cli import _reason_for

        reason = _reason_for(rec, cls, result["weight_shifts"])
    exec_route = hosts.execution_route_block(rec, models_by_key) if rec else None
    fb_route = (
        hosts.execution_route_block(result["fallback"], models_by_key)
        if result["fallback"]
        else None
    )
    return {
        "classification": cls.model_dump(mode="json"),
        **result,
        "reason": reason,
        "gates": gates,
        "prompt": prompt,
        "execution_route": exec_route,
        "fallback_execution_route": fb_route,
    }


def _rust_route_payload(home, task: str, *extra: str) -> dict:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "cli_route_cli", "--", str(home), task, *extra],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout.strip())


@pytest.mark.parametrize("task", TASKS)
def test_route_payload_matches_between_python_and_rust(seeded_home, task):
    python_payload = _python_route_payload(seeded_home, task)
    rust_payload = _rust_route_payload(seeded_home, task)
    assert rust_payload == python_payload, f"mismatch for task: {task!r}"


def test_rust_route_verify_live_matches_python_without_registered_adapters(
    seeded_home, monkeypatch
):
    monkeypatch.setenv("AGENTROUTER_HOME", str(seeded_home))
    task = "Summarize this document"
    python = CliRunner().invoke(app, ["route", task, "--json", "--no-log", "--verify-live"])
    assert python.exit_code == 0, python.output
    expected = json.loads(python.stdout)
    expected.pop("decision_id")
    expected.pop("task")

    rust = _rust_route_payload(seeded_home, task, "--verify-live")

    assert rust == expected
    assert rust["usage_check"]["state"] == "unsupported"


def test_rust_route_persists_python_readable_decision(seeded_home):
    task = "Summarize this document"
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "cli_route_cli",
            "--",
            str(seeded_home),
            task,
            "--save",
        ],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    routed = json.loads(result.stdout)
    conn = store.connect(seeded_home)
    loaded = store.load_decision(conn, routed["decision_id"])
    conn.close()
    assert loaded is not None
    assert loaded["task"] == task
    assert loaded["prompt"] == routed["prompt"]
    assert loaded["classification"] == routed["classification"]
    assert loaded["recommendation"] == routed["recommendation"]


def test_rust_route_respects_configured_weights_and_pricing_policy(seeded_home, monkeypatch):
    (seeded_home / "config.yaml").write_text(
        "weights:\n  w_cap: 0.70\n  w_cost: 0.10\n  w_lat: 0.10\n  w_ctx: 0.10\n"
        "learning: false\npolicy:\n  max_pricing_tier: medium\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENTROUTER_HOME", str(seeded_home))
    task = "Summarize this document"
    python = CliRunner().invoke(app, ["route", task, "--json", "--no-log"])
    assert python.exit_code == 0, python.output
    expected = json.loads(python.stdout)
    expected.pop("decision_id")
    expected.pop("task")
    rust = _rust_route_payload(seeded_home, task)
    assert rust == expected


@pytest.mark.parametrize(
    "config",
    [
        "policy:\n  max_pricing_tier: [high]\n",
        "policy: [high]\n",
        "weights: [0.1, 0.9]\n",
        "weights:\n  w_cap: true\n",
        "[not, a, mapping]\n",
        "policy: [\n",
    ],
)
def test_rust_route_rejects_invalid_config(seeded_home, config):
    (seeded_home / "config.yaml").write_text(config, encoding="utf-8")
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "cli_route_cli",
            "--",
            str(seeded_home),
            "write a function",
        ],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("learning", [True, False])
def test_rust_route_matches_feedback_learning_switch(seeded_home, monkeypatch, learning):
    conn = store.connect(seeded_home)
    for index in range(3):
        decision_id = store.save_decision(conn, f"feedback task {index}", {})
        conn.execute(
            "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (?, ?, ?, ?)",
            (int(decision_id.removeprefix("d_")), "2026-11-09T00:00:00+00:00", 2, "bad"),
        )
    conn.commit()
    conn.close()
    (seeded_home / "config.yaml").write_text(f"learning: {str(learning).lower()}\n")
    monkeypatch.setenv("AGENTROUTER_HOME", str(seeded_home))
    task = "Summarize this document"
    python = CliRunner().invoke(app, ["route", task, "--json", "--no-log"])
    assert python.exit_code == 0, python.output
    expected = json.loads(python.stdout)
    expected.pop("decision_id")
    expected.pop("task")
    rust = _rust_route_payload(seeded_home, task)
    assert rust == expected
    assert any("learned from" in shift for shift in rust["weight_shifts"]) is learning


@pytest.mark.parametrize(
    "control_args",
    [
        ("--vendor", "openai"),
        ("--exclude-vendor", "anthropic"),
        ("--model", "openai/gpt-5.6-terra"),
        ("--host", "openai-api"),
        ("--stable-only",),
        ("--available-only",),
        ("--exclude-host", "codex-cli"),
        ("--max-price", "999"),
        ("--prohibit-tool", "shell"),
    ],
)
def test_rust_route_preserves_control_exclusions(seeded_home, monkeypatch, control_args):
    monkeypatch.setenv("AGENTROUTER_HOME", str(seeded_home))
    task = "Summarize this document"
    python = CliRunner().invoke(app, ["route", task, "--json", "--no-log", *control_args])
    assert python.exit_code in (0, 4), python.output
    expected = json.loads(python.stdout)
    expected.pop("decision_id")
    expected.pop("task")
    rust = _rust_route_payload(seeded_home, task, *control_args)
    assert rust == expected


@pytest.mark.parametrize(
    "extra",
    [
        ("unknown-preference",),
        ("--unknown-flag",),
        ("--prohibit-tool", "made-up-tool"),
        ("--max-price", "NaN"),
        ("--max-price", "inf"),
        ("--max-price", "-1"),
    ],
)
def test_rust_route_fails_closed_on_unknown_controls(seeded_home, extra):
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "cli_route_cli",
            "--",
            str(seeded_home),
            "write a function",
            *extra,
        ],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""
