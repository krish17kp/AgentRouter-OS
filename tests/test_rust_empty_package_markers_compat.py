"""Documentation-only Python package markers export no runtime API."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import agentrouter.evaluation.adapters as adapters
import agentrouter.server as server

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_empty_python_package_exports_match_rust_markers():
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_package_markers_from_json",
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
    expected = {
        "evaluation.adapters": [
            name for name in vars(adapters) if not name.startswith("_") and name != "annotations"
        ],
        "server": [
            name for name in vars(server) if not name.startswith("_") and name != "annotations"
        ],
    }
    assert expected == {"evaluation.adapters": [], "server": []}
    assert json.loads(process.stdout) == expected
