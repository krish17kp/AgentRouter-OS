"""Keep TwinRouterBench's offline full-run contract in Rust and Python sync."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.adapters.twinrouterbench import TwinRouterBenchAdapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_twinrouterbench_full_run_status_matches_python():
    adapter = TwinRouterBenchAdapter()
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_twinrouterbench_status_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == adapter.full_run_status()
