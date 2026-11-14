"""Differential contract tests for the evidence-only Rust harness port."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess

import pytest

from agentrouter import harness

RUST_CRATE_DIR = "rust/agentrouter-cli"
RELEVANT_ENV = ("CLAUDECODE", "GITHUB_ACTIONS", "CI", "TERM", "SHELL")

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


@functools.lru_cache(maxsize=1)
def _built_binary_path() -> str:
    subprocess.run(
        ["cargo", "build", "--quiet", "--bin", "harness_cli"],
        cwd=RUST_CRATE_DIR,
        check=True,
        timeout=180,
    )
    name = "harness_cli.exe" if os.name == "nt" else "harness_cli"
    return os.path.abspath(os.path.join("target", "debug", name))


if shutil.which("cargo") is not None:
    _built_binary_path()


@pytest.mark.parametrize(
    "env_vars",
    [
        {"CLAUDECODE": "1"},
        {"GITHUB_ACTIONS": "true", "CI": "true"},
        {"CI": "true"},
        {"GITHUB_ACTIONS": "false", "CI": "false", "TERM": "xterm"},
        {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
        {},
        {"CLAUDECODE": "1", "CI": "true"},
        {"SOME_UNRELATED_EDITOR_VAR": "1"},
    ],
)
def test_detect_harness_matches_rust(monkeypatch, env_vars):
    for key in RELEVANT_ENV:
        monkeypatch.delenv(key, raising=False)
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    python_result = harness.detect_harness(dict(os.environ))
    result = subprocess.run(
        [_built_binary_path()],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env=dict(os.environ),
    )
    assert json.loads(result.stdout) == {
        "name": python_result.name,
        "evidence": python_result.evidence,
    }
