"""Dataset registry names, profiles, and descriptor lookup match Python."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import registry

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_registry_facade_matches_python_contract():
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_registry_api_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    adapters = [registry.get_adapter(name) for name in registry.dataset_names()]
    expected = {
        "names": registry.dataset_names(),
        "profiles": registry.PROFILES,
        "adapters": [
            {
                "name": name,
                "module": adapter.__class__.__module__.rsplit(".", 1)[-1],
                "class": adapter.__class__.__name__,
                "available": registry.try_get_adapter(name) is not None,
            }
            for name, adapter in zip(registry.dataset_names(), adapters, strict=True)
        ],
        "unknown_is_none": registry.try_get_adapter("not-a-dataset") is None,
        "unknown_error": "unknown dataset 'not-a-dataset'. Known: "
        + ", ".join(registry.dataset_names()),
        "available_count": len(registry.available_adapters()),
    }
    assert json.loads(process.stdout) == expected
