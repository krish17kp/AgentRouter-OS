"""Documentation-only Python package markers export no runtime API."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_empty_python_package_exports_match_rust_markers():
    python = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; import agentrouter.evaluation.adapters as a; "
                "import agentrouter.server as s; "
                "print(json.dumps({'evaluation.adapters': "
                "[n for n in vars(a) if not n.startswith('_') and n != 'annotations'], "
                "'server': [n for n in vars(s) if not n.startswith('_') "
                "and n != 'annotations']}))"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=30,
        check=True,
    )
    expected = json.loads(python.stdout)
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
    assert expected == {"evaluation.adapters": [], "server": []}
    assert json.loads(process.stdout) == expected
