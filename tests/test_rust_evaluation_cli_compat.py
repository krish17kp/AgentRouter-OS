"""Smoke and contract coverage for the Rust evaluation CLI executable."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.runner import run as python_run

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "agentrouter-evaluate",
            "-p",
            "agentrouter-evaluation",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def test_rust_evaluation_cli_lists_registered_datasets():
    process = _cli("list-datasets", "--json")
    assert process.returncode == 0, process.stderr
    rows = json.loads(process.stdout)
    assert [row["name"] for row in rows] == [
        "agentrouter-gold",
        "clinc150",
        "banking77",
        "massive",
        "longbench-v2",
        "swebench",
        "llmrouterbench",
        "twinrouterbench",
    ]
    assert all(row["availability"] in {"ready", "fixture_only", "skipped_external"} for row in rows)


def test_rust_evaluation_cli_run_matches_python_report_without_artifacts():
    process = _cli(
        "run",
        "--dataset",
        "agentrouter-gold",
        "--limit",
        "7",
        "--seed",
        "12",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    expected = python_run(dataset="agentrouter-gold", limit=7, seed=12)
    expected.pop("environment")
    expected.pop("classification")
    actual.pop("environment")
    assert actual == expected


def test_rust_evaluation_cli_reports_external_blocker_without_fixture_fallback():
    process = _cli(
        "run",
        "--dataset",
        "clinc150",
        "--source",
        "real",
        "--no-artifacts",
        "--json",
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["n_cases"] == 0
    assert result["datasets"]["clinc150"]["status"] == "SKIPPED_EXTERNAL"
    assert "fixture_only" in result["datasets"]["clinc150"]["availability"]
    assert result["datasets"]["clinc150"]["blocker"]


def test_rust_evaluation_cli_rejects_incomplete_release_gate_request():
    process = _cli("run", "--require-release-ready", "--no-artifacts", "--json")
    assert process.returncode == 2
    assert "requires --all" in process.stderr
