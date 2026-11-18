"""Full Python/Rust adapter contract check for LLMRouterBench."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.llmrouterbench import LLMRouterBenchAdapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_llmrouterbench_adapter_matches_python(monkeypatch):
    adapter = LLMRouterBenchAdapter()
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    metadata = asdict(adapter.metadata())
    metadata["languages"] = list(metadata["languages"])
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_llmrouterbench_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"path": str(adapter.fixture_path), "metadata": metadata}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    actual = json.loads(process.stdout)
    cases = adapter.load()
    with pytest.raises(evaluation_base.SkippedExternal) as real_error:
        adapter.load(source=evaluation_base.REAL)
    assert actual == {
        "metadata": metadata,
        "availability": adapter.availability().value,
        "real_available": adapter.real_availability()[0],
        "real_reason": adapter.real_availability()[1],
        "describe": adapter.describe(),
        "model_mapping_required": adapter.model_mapping_required(),
        "model_mapping_note": adapter.describe()["model_mapping_note"],
        "full_run_status": adapter.full_run_status(),
        "cases": [case.model_dump(mode="json") for case in cases],
        "sample": [case.model_dump(mode="json") for case in adapter.sample(limit=4, seed=3)],
        "checksum": adapter.checksum(),
        "real_error": str(real_error.value),
    }
