"""Rust seed-home probe matches Python's non-forced `agentrouter init`."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess

import pytest
from typer.testing import CliRunner

from agentrouter.cli import app

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
runner = CliRunner()


def _rust_init(home):
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "init_cli", "--", str(home)],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


def _tables(home):
    with sqlite3.connect(home / "agentrouter.db") as conn:
        return {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }


def test_rust_init_matches_python_seed_and_is_idempotent(tmp_path, monkeypatch):
    python_home = tmp_path / "python"
    rust_home = tmp_path / "rust"
    monkeypatch.setenv("AGENTROUTER_HOME", str(python_home))

    first_python = runner.invoke(app, ["init"])
    first_rust = _rust_init(rust_home)
    assert first_python.exit_code == 0, first_python.output
    assert first_rust.stdout.replace(str(rust_home), "<HOME>") == first_python.stdout.replace(
        str(python_home), "<HOME>"
    )
    for relative in ("config.yaml", "registry/providers.yaml", "registry/models.yaml"):
        assert (rust_home / relative).read_bytes() == (python_home / relative).read_bytes()
    assert {"decisions", "feedback"}.issubset(_tables(rust_home))

    second_python = runner.invoke(app, ["init"])
    second_rust = _rust_init(rust_home)
    assert second_python.exit_code == 0, second_python.output
    assert second_rust.stdout.replace(str(rust_home), "<HOME>") == second_python.stdout.replace(
        str(python_home), "<HOME>"
    )
