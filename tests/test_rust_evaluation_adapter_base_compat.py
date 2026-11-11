"""Differential tests for shared fixture-backed evaluation adapter behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.banking77 import Banking77Adapter
from agentrouter.evaluation.adapters.clinc150 import CLINC150Adapter
from agentrouter.evaluation.adapters.longbench_v2 import LongBenchV2Adapter
from agentrouter.evaluation.adapters.massive import MassiveAdapter
from agentrouter.evaluation.adapters.swebench import SWEBenchAdapter
from agentrouter.evaluation.adapters.twinrouterbench import TwinRouterBenchAdapter
from agentrouter.evaluation.base import SkippedExternal

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = [
    CLINC150Adapter,
    Banking77Adapter,
    MassiveAdapter,
    LongBenchV2Adapter,
    SWEBenchAdapter,
    TwinRouterBenchAdapter,
]


def _rust_surface(adapter, metadata: dict) -> dict:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_adapter_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "path": str(adapter.fixture_path),
                "metadata": metadata,
                "hf_repo": adapter.hf_repo,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


def _python_surface(adapter):
    cases = adapter.load()
    try:
        adapter.load(source=evaluation_base.REAL)
    except SkippedExternal as error:
        real_error = str(error)
    else:  # pragma: no cover - datasets availability is forced off in this test
        raise AssertionError("real adapter load unexpectedly ran")
    return {
        "metadata": _metadata_dict(adapter),
        "availability": adapter.availability().value,
        "real_available": adapter.real_availability()[0],
        "real_reason": adapter.real_availability()[1],
        "describe": adapter.describe(),
        "cases": [case.model_dump(mode="json") for case in cases],
        "sample": [case.model_dump(mode="json") for case in adapter.sample(limit=4, seed=3)],
        "checksum": adapter.checksum(),
        "real_error": real_error,
    }


def _metadata_dict(adapter) -> dict:
    metadata = asdict(adapter.metadata())
    metadata["languages"] = list(metadata["languages"])
    return metadata


@pytest.mark.parametrize("adapter_type", ADAPTERS, ids=lambda cls: cls.__name__)
def test_rust_fixture_adapter_base_matches_python(adapter_type, monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    adapter = adapter_type()
    metadata = _metadata_dict(adapter)

    assert _rust_surface(adapter, metadata) == _python_surface(adapter)
