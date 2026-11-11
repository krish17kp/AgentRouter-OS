"""Differential checks for the dormant learned context-band inference path."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.context_model import feature_vector, load_model

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")

PROMPTS = [
    "Review this 120k-token repository",
    "Summarize 12000 tokens",
    "Analyze 250 source files in the current service",
    "Refactor the billing subsystem already in use",
    "Audit the existing parser",
    "Review and harden this deployment",
    "Build an ingestion pipeline for the warehouse",
    "Explain the purpose of workflow retries",
    "Create a disposable demo service",
    "Review the entire monorepo archive",
    "Summarize the protocol document",
    "Explain the following",
    "Write a brief response",
    "Investigate and reconcile existing partitions for 300 files",
    "Analyze this résumé in Japanese: 42k tokens",
]


def _rust(prompt: str) -> dict:
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--manifest-path",
            "rust/agentrouter-classifier/Cargo.toml",
            "--bin",
            "context_model_cli",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout)


def test_rust_model_artifact_matches_python_source_of_truth():
    python_artifact = ROOT / "agentrouter/benchmarks/context_band_model_v1.json"
    rust_artifact = ROOT / "rust/agentrouter-classifier/resources/context_band_model_v1.json"
    assert rust_artifact.read_bytes() == python_artifact.read_bytes()


@pytest.mark.parametrize("prompt", PROMPTS)
def test_context_model_features_match_python(prompt):
    result = _rust(prompt)
    assert result["features"] == feature_vector(prompt)


@pytest.mark.parametrize("prompt", PROMPTS)
def test_context_model_prediction_matches_python(prompt):
    rust = _rust(prompt)["prediction"]
    python = load_model().predict(prompt)
    assert rust["band"] == python[0]
    assert rust["confidence"] == pytest.approx(python[1], abs=1e-12)
