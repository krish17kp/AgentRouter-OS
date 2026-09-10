"""Shared fixtures for the AgentRouter OS test suite.

Only fixtures with byte-for-byte identical bodies across multiple test files
belong here. Files whose `home`-style setup differs (different env var
deleted, a nested subdirectory, or no `init` invocation at all) keep their
own local fixture; that variation is real test intent, not duplication.

This file also carries a suite-wide safety net: no test may write into the
developer's real home. That exists because of a mistake made while writing
TASK-019's tests. A test took `(plugin, tmp_path)` but not the `root` fixture,
so `AGENTROUTER_PLUGIN_ROOT` was never set, `plugins.dest_root()` fell back to
`Path.home()`, and the test created a symlink inside the developer's ACTUAL
`~/.claude/skills/`. It passed. It kept passing. What it broke was an unrelated
test in another file, which is a terrible way to find out.

The plugin subsystem is the one part of AgentRouter that writes outside the
project, so its tests are the ones that can damage the machine they run on. A
missing fixture argument is silent, and every plugin test would have to remember
the convention. This checks the outcome instead: after every test, the real
plugin destinations must be exactly as they were before the run.
"""

from __future__ import annotations

from pathlib import Path

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


def _real_destinations() -> list[Path]:
    """The paths the shipped plugins target in a real home. Never written by tests."""
    home = Path.home()
    return [home / ".claude" / "skills" / "agentrouter", home / ".codex" / "AGENTS.md"]


@pytest.fixture(autouse=True)
def _never_touch_the_real_home():
    before = {path: path.exists() or path.is_symlink() for path in _real_destinations()}
    yield
    for path, existed in before.items():
        now = path.exists() or path.is_symlink()
        if now and not existed:
            # Remove it so one leaky test does not cascade into every later one,
            # then fail loudly naming the fixture that was missing.
            try:
                if path.is_dir() and not path.is_symlink():
                    for child in sorted(path.iterdir(), reverse=True):
                        child.unlink()
                    path.rmdir()
                else:
                    path.unlink()
            except OSError:  # pragma: no cover - cleanup is best-effort
                pass
            pytest.fail(
                f"this test wrote into the real home at {path}. Plugin tests must "
                "take the `root` fixture (it sets AGENTROUTER_PLUGIN_ROOT); without "
                "it, dest_root() falls back to Path.home()."
            )
        assert now == existed, f"a test changed the real home at {path}"
