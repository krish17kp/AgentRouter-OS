"""Public annotation package constants agree between Python and Rust."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter import annotation

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_annotation_package_constants_match_rust_facade():
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_public_api_from_json",
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
        "SCHEMA_VERSION": annotation.SCHEMA_VERSION,
        "CATEGORIES": list(annotation.CATEGORIES),
        "SPLITS": list(annotation.SPLITS),
    }
    assert json.loads(process.stdout) == expected
