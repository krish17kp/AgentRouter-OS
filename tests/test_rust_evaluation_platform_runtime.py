"""The Rust scorecard discovers its command surface from the installed CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.evaluators.platform import _command_names, _group_names

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _cargo(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=180,
        check=False,
    )


def test_rust_full_evaluation_uses_the_running_cli_surface():
    surface_process = _cargo(
        "-p",
        "agentrouter-cli",
        "--bin",
        "agentrouter",
        "--",
        "__evaluation_surface",
    )
    assert surface_process.returncode == 0, surface_process.stderr
    surface = json.loads(surface_process.stdout)
    assert surface["commands"] == sorted(_command_names())
    # `contract` is a hidden Python Typer group and is not exposed by the Rust
    # CLI. The platform evaluator's score is based only on its declared groups.
    assert set(surface["groups"]) == _group_names() - {"contract"}

    evaluation_process = _cargo(
        "-p",
        "agentrouter-evaluation",
        "--bin",
        "agentrouter-evaluate",
        "--",
        "run",
        "--profile",
        "fast",
        "--limit",
        "3",
        "--all",
        "--json",
        "--no-artifacts",
    )
    assert evaluation_process.returncode == 0, evaluation_process.stderr
    report = json.loads(evaluation_process.stdout)
    platform = report["dimensions"]["cli_platform"]
    assert platform["score"] == 1.0
    assert platform["detail"]["commands_found"] == surface["commands"]
    assert platform["detail"]["groups_found"] == sorted(surface["groups"])
