"""Shared fixtures for the AgentRouter OS test suite.

Only fixtures with byte-for-byte identical bodies across multiple test files
belong here. Files whose `home`-style setup differs (different env var
deleted, a nested subdirectory, or no `init` invocation at all) keep their
own local fixture; that variation is real test intent, not duplication.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from agentrouter.cli import app as _cli_app

_runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolated AGENTROUTER_HOME with no API key, initialized via the real `init` command."""
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert _runner.invoke(_cli_app, ["init"]).exit_code == 0
    return tmp_path
