"""Differential checks for the historical classifier gold-set evaluator."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from agentrouter import evaluate as python_evaluator

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "agentrouter" / "benchmarks" / "classifier_gold_v1.yaml"
ROUTING_GOLD = ROOT / "agentrouter" / "benchmarks" / "routing_gold_v1.yaml"


def _rust(request: dict) -> dict:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "legacy_gold_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)["value"]


def _rust_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-evaluation",
            "--bin",
            "agentrouter-evaluate",
            "--",
            *arguments,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def test_rust_legacy_gold_loader_and_full_classifier_report_match_python(tmp_path):
    cases = python_evaluator.load_gold(GOLD)
    expected = python_evaluator.evaluate(GOLD)
    assert _rust({"operation": "grade_cases", "cases": cases}) == expected
    assert _rust({"operation": "evaluate_gold", "path": str(GOLD)}) == expected

    python_dir = tmp_path / "python"
    rust_dir = tmp_path / "rust"
    python_paths = python_evaluator.write_artifacts(expected, python_dir)
    rust_result = _rust(
        {"operation": "write_artifacts", "report": expected, "out_dir": str(rust_dir)}
    )
    assert [Path(path).name for path in rust_result["paths"]] == [
        path.name for path in python_paths
    ]
    assert json.loads((rust_dir / "evaluation.json").read_text(encoding="utf-8")) == json.loads(
        python_paths[0].read_text(encoding="utf-8")
    )
    assert (rust_dir / "evaluation.md").read_text(encoding="utf-8") == python_paths[1].read_text(
        encoding="utf-8"
    )
    assert (rust_dir / "failures.csv").read_bytes() == python_paths[2].read_bytes()


def test_rust_legacy_grader_matches_partial_labels_and_empty_dimensions():
    cases = [
        {
            "id": "multi-label",
            "prompt": "Refactor the API module and add tests",
            "task_type": ["coding", "reasoning"],
            "complexity": ["medium", "high"],
            "risk": ["low", "medium"],
            "tools": ["file-edit", "shell"],
        },
        {"id": "ungraded", "prompt": "Tell me a fun fact"},
        {
            "id": "wrong-labels",
            "prompt": "Write a short announcement",
            "task_type": "coding",
            "risk": "high",
            "tools": [],
        },
    ]
    assert _rust({"operation": "grade_cases", "cases": cases}) == python_evaluator.grade_cases(
        cases
    )


def test_rust_legacy_routing_gold_matches_python_scenarios():
    document = yaml.safe_load(ROUTING_GOLD.read_text(encoding="utf-8"))
    expected = python_evaluator.evaluate_routing(ROUTING_GOLD)
    assert _rust({"operation": "grade_routing", "scenarios": document["scenarios"]}) == expected
    assert _rust({"operation": "evaluate_routing", "path": str(ROUTING_GOLD)}) == expected


def test_rust_evaluation_cli_exposes_legacy_and_routing_gold_commands():
    legacy = _rust_cli("legacy-gold", "--no-artifacts", "--json")
    assert legacy.returncode == 0, legacy.stderr
    legacy_report = json.loads(legacy.stdout)
    assert legacy_report["n_cases"] >= 150
    assert "cases" not in legacy_report

    routing = _rust_cli("routing-gold", "--json")
    assert routing.returncode == 0, routing.stderr
    assert json.loads(routing.stdout)["all_pass"] is True
