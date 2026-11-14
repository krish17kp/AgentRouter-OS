"""End-to-end differential checks for the registered Rust evaluation runner."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.runner import run as python_run

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust_run(request):
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_registered_runner_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"project_root": str(ROOT), **request}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 7, "seed": 12},
        {"profile": "nightly", "limit": 4, "seed": 3},
        {"dataset": "massive", "languages": ["fr", "en"], "limit": 3, "seed": 5},
    ],
)
def test_rust_registered_runner_matches_python_report(options):
    expected = python_run(**options)
    actual = _rust_run(options)
    assert {key: value for key, value in actual.items() if key != "environment"} == {
        key: value for key, value in expected.items() if key != "environment"
    }


def test_rust_registered_real_run_records_blockers_without_fallback(monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    request = {"profile": "nightly", "source": "real", "limit": 4, "seed": 3}
    expected = python_run(**request)
    actual = _rust_run(request)
    assert {key: value for key, value in actual.items() if key != "environment"} == {
        key: value for key, value in expected.items() if key != "environment"
    }
