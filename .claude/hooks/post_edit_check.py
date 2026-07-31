#!/usr/bin/env python3
"""PostToolUse check for AgentRouter OS.

After a Write/Edit to a Python source file, run the smallest relevant lint
(`ruff check <file>`). Surfaces issues back to Claude (exit 2) so they get fixed
immediately, instead of running the whole suite after every keystroke.

Fails OPEN: if ruff is missing or times out, allow (never wedge the session).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hook_utils import allow, edited_path, read_event

TIMEOUT_S = 30


def main() -> None:
    event = read_event()
    path = edited_path(event)
    if not path or not path.endswith(".py"):
        allow()

    p = Path(path)
    # Only lint project source; skip generated/vendored/hook files themselves.
    parts = set(p.parts)
    if not ({"agentrouter", "tests"} & parts) or ".venv" in parts:
        allow()

    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "ruff", "check", str(p)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        allow()

    if result.returncode != 0:
        out = (result.stdout or result.stderr or "").strip()
        print(f"[post_edit_check] ruff issues in {p.name}:\n{out}", file=sys.stderr)
        sys.exit(2)
    allow()


if __name__ == "__main__":
    main()
