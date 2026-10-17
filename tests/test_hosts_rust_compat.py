"""Python/Rust host-detection compatibility check for the R3 milestone.

`hosts.detect_host()` reads the environment and filesystem rather than
taking a self-contained input, so this test controls that environment
(a tempdir HOME, a fake PATH entry, explicit env vars) identically for
both the direct Python call and the Rust `detect_host_cli` subprocess,
then diffs the resulting status dict.

Skips (does not fail) when `cargo` isn't on PATH, matching the other
Rust compatibility tests' convention.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import stat
import subprocess
from dataclasses import asdict

import pytest

from agentrouter import hosts

RUST_CRATE_DIR = "rust/agentrouter-hosts"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


@functools.lru_cache(maxsize=1)
def _built_binary_path() -> str:
    """Build the bin once under the *real* environment (cargo itself needs a
    working PATH), so individual tests can invoke the compiled artifact
    directly under a deliberately restricted env without breaking cargo's
    own toolchain lookup.
    """
    subprocess.run(
        ["cargo", "build", "--quiet", "--bin", "detect_host_cli"],
        cwd=RUST_CRATE_DIR,
        check=True,
        timeout=180,
    )
    # Workspace target dir is at the repo root, not under RUST_CRATE_DIR.
    return os.path.abspath(os.path.join("target", "debug", "detect_host_cli"))


def _rust_status(host: str, required_command: str | None, env: dict) -> dict:
    args = [_built_binary_path(), host]
    if required_command is not None:
        args.append(required_command)
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=30, check=True, env=env
    )
    return json.loads(result.stdout.strip())


if shutil.which("cargo") is not None:
    # Build once, before any test's monkeypatch can touch PATH/HOME, so the
    # cargo invocation itself always runs under a real, working environment.
    _built_binary_path()


def _python_status(host: str, required_command: str | None) -> dict:
    return asdict(hosts.detect_host(host, required_command))


@pytest.mark.parametrize(
    "host,env_vars",
    [
        ("manual", {}),
        ("openrouter", {}),
        ("openrouter", {"OPENROUTER_API_KEY": "sk-test-value"}),
        ("openrouter", {"OPENROUTER_API_KEY": "   "}),
        ("unrecognized-made-up-host", {}),
    ],
)
def test_detect_host_matches_without_cli_filesystem_state(monkeypatch, host, env_vars, tmp_path):
    for key in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HOME", str(tmp_path))

    python_result = _python_status(host, None)
    rust_result = _rust_status(host, None, dict(os.environ))
    assert rust_result == python_result


def test_cli_host_missing_binary_matches(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path))  # empty PATH entry, binary can't be found
    cmd = "definitely-not-a-real-binary-xyz"

    python_result = _python_status("claude-code", cmd)
    rust_result = _rust_status("claude-code", cmd, dict(os.environ))
    assert rust_result == python_result


def test_cli_host_installed_then_configured_then_authenticated_matches(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_cli = bin_dir / "fake-claude-cli"
    fake_cli.write_text("#!/bin/sh\necho ok\n")
    fake_cli.chmod(fake_cli.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    # Stage 1: binary on PATH, no config dir yet -> installed.
    python_result = _python_status("claude-code", "fake-claude-cli")
    rust_result = _rust_status("claude-code", "fake-claude-cli", dict(os.environ))
    assert rust_result == python_result
    assert python_result["state"] == "installed"

    # Stage 2: config dir exists but no credential file -> configured.
    (home / ".claude").mkdir()
    python_result = _python_status("claude-code", "fake-claude-cli")
    rust_result = _rust_status("claude-code", "fake-claude-cli", dict(os.environ))
    assert rust_result == python_result
    assert python_result["state"] == "configured"

    # Stage 3: credential file present -> authenticated.
    (home / ".claude" / ".credentials.json").write_text("{}")
    python_result = _python_status("claude-code", "fake-claude-cli")
    rust_result = _rust_status("claude-code", "fake-claude-cli", dict(os.environ))
    assert rust_result == python_result
    assert python_result["state"] == "authenticated"
