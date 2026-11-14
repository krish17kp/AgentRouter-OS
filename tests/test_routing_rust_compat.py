"""Python/Rust routing-engine compatibility check for the R3 milestone.

Runs every scenario in the real routing gold benchmark
(`agentrouter/benchmarks/routing_gold_v1.yaml` — the same fixture
`test_routing_benchmark.py::test_routing_gold_all_scenarios_pass` grades)
through `agentrouter.engine.route()` (Python, release-gate authority) and
the Rust `agentrouter-routing` port (via the `route_cli` bin), and asserts
the full result dict matches field-for-field.

Skips (does not fail) when `cargo` isn't on PATH, matching the R1/R2
compat tests' convention.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

import agentrouter
from agentrouter.engine import route
from agentrouter.evaluate import _apply_pricing_cap, build_classification
from agentrouter.schema import ModelEntry

RUST_CRATE_DIR = "rust/agentrouter-routing"
GOLD_PATH = Path(agentrouter.__file__).parent / "benchmarks" / "routing_gold_v1.yaml"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _scenario_ids() -> list[str]:
    doc = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    return [s["id"] for s in doc["scenarios"]]


def _python_route_json(scenario_id: str) -> dict:
    doc = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    scenario = next(s for s in doc["scenarios"] if s["id"] == scenario_id)
    models = [ModelEntry(**m) for m in scenario["models"]]
    models = _apply_pricing_cap(models, scenario.get("max_pricing_tier"))
    cls = build_classification(scenario.get("classification", {}))
    return route(models, cls)


def _rust_route_json(scenario_id: str) -> dict:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "route_cli", "--", str(GOLD_PATH), scenario_id],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout.strip())


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_route_matches_between_python_and_rust(scenario_id):
    python_result = _python_route_json(scenario_id)
    rust_result = _rust_route_json(scenario_id)
    assert rust_result == python_result, f"mismatch for scenario: {scenario_id!r}"


def test_route_preserves_unbounded_model_and_classification_token_counts(tmp_path):
    source = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    model = dict(source["scenarios"][0]["models"][0])
    model["model_id"] = "arbitrary-context"
    # These large integers sit just below a 2x context ratio. Python's int
    # division rounds the ratio to 2.0; Rust must preserve that score boundary.
    model["context_window"] = str(2**100 - 1)
    classification = {
        "task_type": "coding",
        "complexity": "medium",
        "risk": "low",
        "context_tokens": str(2**99),
        "tool_needs": [],
    }
    scenario = {
        "id": "arbitrary-context",
        "models": [model],
        "classification": classification,
    }
    path = tmp_path / "routing.yaml"
    path.write_text(yaml.safe_dump({"scenarios": [scenario]}), encoding="utf-8")

    python_classification = {**classification, "context_tokens": 2**99}
    python_result = route([ModelEntry(**model)], build_classification(python_classification))
    rust = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "route_cli", "--", str(path), scenario["id"]],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert json.loads(rust.stdout) == python_result
