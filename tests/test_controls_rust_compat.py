"""Python/Rust `controls.py` compatibility check for the R3 milestone.

Runs a handful of `RouteControls` filters against the real routing gold
benchmark's scenario model lists (`agentrouter/benchmarks/routing_gold_v1.yaml`)
through `agentrouter.controls.apply_controls()` (Python, release-gate
authority) and the Rust `agentrouter-policy` port (via the `controls_cli`
bin), asserting kept model keys and dropped reasons match exactly.

Skips (does not fail) when `cargo` isn't on PATH, matching the other
R1/R2/R3 compat tests' convention.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

import agentrouter
from agentrouter.controls import RouteControls, apply_controls
from agentrouter.schema import ModelEntry

RUST_CRATE_DIR = "rust/agentrouter-policy"
GOLD_PATH = Path(agentrouter.__file__).parent / "benchmarks" / "routing_gold_v1.yaml"
SCENARIO_ID = "r-tool-filter"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")

CASES = [
    {},
    {"vendor": ["p"]},
    {"exclude_vendor": ["p"]},
    {"model": "full-tools"},
    {"stable_only": True},
    {"max_price": 1.0},
    {"max_price": 100.0},
    {"prohibit_tool": ["shell"]},
    {"available_only": True},
]


def _scenario_models() -> list[dict]:
    doc = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    scenario = next(s for s in doc["scenarios"] if s["id"] == SCENARIO_ID)
    return scenario["models"]


def _python_result(case: dict) -> dict:
    models = [ModelEntry(**m) for m in _scenario_models()]
    controls = RouteControls(
        vendor=tuple(case.get("vendor", ())),
        exclude_vendor=tuple(case.get("exclude_vendor", ())),
        model=case.get("model"),
        host=tuple(case.get("host", ())),
        exclude_host=tuple(case.get("exclude_host", ())),
        max_price=case.get("max_price"),
        stable_only=case.get("stable_only", False),
        available_only=case.get("available_only", False),
        prohibit_tool=tuple(case.get("prohibit_tool", ())),
    )
    kept, dropped = apply_controls(models, controls)
    return {"kept": [m.key for m in kept], "dropped": dropped}


def _rust_result(case: dict) -> dict:
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--bin",
            "controls_cli",
            "--",
            str(GOLD_PATH),
            SCENARIO_ID,
            json.dumps(case),
        ],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout.strip())


@pytest.mark.parametrize("case", CASES, ids=[json.dumps(c) for c in CASES])
def test_controls_match_between_python_and_rust(case):
    assert _rust_result(case) == _python_result(case), f"mismatch for case: {case!r}"
