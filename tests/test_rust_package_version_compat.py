"""The Rust package facade reads the same canonical distribution version."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import agentrouter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_package_version_matches_python_distribution():
    process = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "package_version_from_json", "-p", "agentrouter-core"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == agentrouter.__version__
