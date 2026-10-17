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

from agentrouter import hosts, store
from agentrouter.classifier import classify
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


def _rust_route_payload(home, task: str) -> dict:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "cli_route_cli", "--", str(home), task],
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
