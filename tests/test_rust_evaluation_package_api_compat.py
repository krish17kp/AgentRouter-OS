"""Public package exports of the Rust and Python evaluation facades agree."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import agentrouter.evaluation as evaluation

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_package_public_exports_match_rust_facade():
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_public_api_from_json",
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
    assert json.loads(process.stdout) == evaluation.__all__
