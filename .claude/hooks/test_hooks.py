"""Unit tests for AgentRouter OS Claude Code hooks.

Run: python -m pytest .claude/hooks/test_hooks.py -q
Invokes each hook as a subprocess with a JSON event on stdin and asserts the
exit code (0 = allow, 2 = block).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).parent


def run_hook(script: str, event: dict) -> int:
    proc = subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


# ---- pre_tool_guard ----


def test_blocks_git_push():
    assert run_hook("pre_tool_guard.py", bash("git push origin main")) == 2


def test_blocks_git_commit():
    assert run_hook("pre_tool_guard.py", bash("git commit -m x")) == 2


def test_blocks_rm_rf():
    assert run_hook("pre_tool_guard.py", bash("rm -rf data/")) == 2


def test_blocks_shell_true():
    assert run_hook("pre_tool_guard.py", bash("python -c 'subprocess.run(x, shell=True)'")) == 2


def test_blocks_secret_print():
    assert run_hook("pre_tool_guard.py", bash("echo $OPENAI_API_KEY")) == 2


def test_blocks_deploy():
    assert run_hook("pre_tool_guard.py", bash("railway up")) == 2


def test_blocks_publish():
    assert run_hook("pre_tool_guard.py", bash("twine upload dist/*")) == 2


def test_allows_safe_command():
    assert run_hook("pre_tool_guard.py", bash("python -m pytest -q")) == 0


def test_allows_git_read():
    assert run_hook("pre_tool_guard.py", bash("git log --oneline -5")) == 0


def test_allows_non_bash():
    assert run_hook("pre_tool_guard.py", {"tool_name": "Read", "tool_input": {}}) == 0


def test_pre_guard_fails_open_on_empty():
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "pre_tool_guard.py")],
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


# ---- stop_gate ----


def test_stop_allows_when_no_state(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


def test_stop_blocks_ready_without_passing(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "PRODUCTION_READY", "last_test_results": {"result": "3 failed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2


def test_stop_allows_ready_with_passing(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "PRODUCTION_READY", "last_test_results": {"result": "371 passed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


def test_stop_allows_non_ready_status(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "BLOCKED_EXTERNAL", "last_test_results": {"result": "371 passed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
