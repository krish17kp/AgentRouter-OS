"""Offline differential tests for the Rust AgentRouter gold adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.base import AdapterError

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust_load(path: Path) -> dict:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_gold_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"path": str(path)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def _python_surface(path: Path) -> dict:
    adapter = AgentRouterGoldAdapter(path)
    try:
        cases = adapter.load()
    except AdapterError as error:
        return {"error": str(error), "availability": adapter.availability().value}
    metadata = asdict(adapter.metadata())
    metadata["languages"] = list(metadata["languages"])
    return {
        "cases": [case.model_dump(mode="json") for case in cases],
        "metadata": metadata,
        "availability": adapter.availability().value,
        "describe": adapter.describe(),
        "checksum": adapter.checksum(),
        "sample": [case.model_dump(mode="json") for case in adapter.sample(limit=20, seed=5)],
        "all_sample": [case.model_dump(mode="json") for case in adapter.sample(seed=5)],
        "empty_sample": [case.model_dump(mode="json") for case in adapter.sample(limit=0, seed=5)],
    }


def test_rust_gold_adapter_matches_all_committed_cases():
    path = ROOT / "agentrouter" / "benchmarks" / "classifier_gold_v1.yaml"
    python_result = _python_surface(path)
    rust_result = _rust_load(path)

    assert len(rust_result["cases"]) == 165
    assert rust_result == python_result


def test_rust_gold_adapter_matches_python_defaults_and_derived_approval(tmp_path: Path):
    path = tmp_path / "gold.yaml"
    path.write_text(
        "version: 7\n"
        "cases:\n"
        "  - id: custom-1\n"
        '    prompt: "Résumé punctuation — check!"\n'
        "    risk: [low, high]\n"
        "    unrelated_metadata: ignored by both adapters\n",
        encoding="utf-8",
    )
    assert _rust_load(path) == _python_surface(path)


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "cases: {}\n",
        "cases:\n  - id: duplicate\n    prompt: First task\n"
        "  - id: duplicate\n    prompt: Second task\n",
        "cases:\n  - id: one\n    prompt: Same task!\n  - id: two\n    prompt: same task\n",
    ],
    ids=["missing-file", "invalid-document", "duplicate-id", "duplicate-task"],
)
def test_rust_gold_adapter_matches_python_error_categories(tmp_path: Path, contents: str | None):
    path = tmp_path / "gold.yaml"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")

    assert _rust_load(path) == _python_surface(path)
