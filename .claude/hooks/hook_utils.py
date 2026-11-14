"""Shared helpers for AgentRouter OS Claude Code hooks.

Hooks receive a JSON event on stdin and signal decisions via exit code:
  0 = allow / no-op, 2 = block (stderr is shown to Claude).
Kept dependency-free and cross-platform (Windows + Linux).
"""

from __future__ import annotations

import json
import sys
from typing import Any


def read_event() -> dict[str, Any]:
    """Parse the hook JSON event from stdin. Returns {} on any parse failure."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def tool_name(event: dict[str, Any]) -> str:
    return str(event.get("tool_name") or event.get("toolName") or "")


def tool_input(event: dict[str, Any]) -> dict[str, Any]:
    ti = event.get("tool_input") or event.get("toolInput") or {}
    return ti if isinstance(ti, dict) else {}


def bash_command(event: dict[str, Any]) -> str:
    """The command string for a Bash tool call, else ''."""
    if tool_name(event) != "Bash":
        return ""
    return str(tool_input(event).get("command", ""))


def edited_path(event: dict[str, Any]) -> str:
    """The file_path for a Write/Edit tool call, else ''."""
    if tool_name(event) not in ("Write", "Edit", "NotebookEdit"):
        return ""
    ti = tool_input(event)
    return str(ti.get("file_path") or ti.get("filePath") or "")


def block(message: str) -> None:
    """Block the tool call: message to stderr, exit code 2."""
    print(message, file=sys.stderr)
    sys.exit(2)


def allow() -> None:
    sys.exit(0)
