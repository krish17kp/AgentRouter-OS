"""Python/Rust parity for stored decision inspection and prompt regeneration."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from agentrouter import store
from agentrouter.cli import app

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
runner = CliRunner()


@pytest.fixture()
def decision(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("AGENTROUTER_HOME", str(home))
    initialized = runner.invoke(app, ["init"])
    assert initialized.exit_code == 0, initialized.output
    routed = runner.invoke(app, ["route", "Summarize this report", "--json"])
    assert routed.exit_code == 0, routed.output
    return home, json.loads(routed.stdout)["decision_id"]


def rust_decision(home, op, decision_id, *extra):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "decision_cli",
            "--",
            str(home),
            op,
            decision_id,
            *extra,
        ],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_rust_explain_json_matches_python_store(decision):
    home, decision_id = decision
    result = rust_decision(home, "explain", decision_id)
    assert result.returncode == 0, result.stderr
    conn = store.connect(home)
    expected = store.load_decision(conn, decision_id)
    conn.close()
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("tool", [None, "openai/other-model"])
def test_rust_prompt_from_decision_matches_python_cli(decision, tool):
    home, decision_id = decision
    args = ["prompt", "generate", "--from", decision_id]
    if tool:
        args.extend(["--tool", tool])
    expected = runner.invoke(app, args)
    assert expected.exit_code == 0, expected.output
    result = rust_decision(home, "prompt", decision_id, *([tool] if tool else []))
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected.stdout.removesuffix("\n")


def test_rust_explain_missing_decision_is_nonzero(decision):
    home, _decision_id = decision
    result = rust_decision(home, "explain", "d_99999")
    assert result.returncode == 2
    assert result.stderr == "No decision found with id 'd_99999'.\n"
