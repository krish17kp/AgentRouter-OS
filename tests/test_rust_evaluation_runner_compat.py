"""Offline Rust runner matches Python grading and dataset-quality reports."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.grading import grade
from agentrouter.evaluation.provenance import dataset_quality

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_offline_runner_matches_python_classification_grade():
    cases = AgentRouterGoldAdapter().load()[:25]
    environment = {
        "agentrouter_version": "0.5.0rc1",
        "python": "3.12.15",
        "platform": "fixture-platform",
        "git_sha": "abc123",
    }
    datasets = {"agentrouter-gold": {"status": "fixture_only", "n": len(cases)}}
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_runner_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "cases": [case.model_dump(mode="json") for case in cases],
                "profile": "fast",
                "seed": 0,
                "source": "fixture",
                "environment": environment,
                "datasets": datasets,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    expected = grade(cases)
    expected.update(
        {
            "environment": environment,
            "datasets": datasets,
            "profile": "fast",
            "dataset_quality": dataset_quality(cases),
            "seed": 0,
            "source": "fixture",
        }
    )
    assert json.loads(process.stdout) == expected
