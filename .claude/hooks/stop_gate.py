#!/usr/bin/env python3
"""Stop-gate for AgentRouter OS.

Blocks session completion when the persisted loop state contradicts a "ready"
claim (command.md section 6). Deterministic and conservative: it only blocks on
a clear contradiction, never merely because state is missing (that would trap
the session).

Blocks (exit 2) when LOOP_STATE.json asserts a READY / COMPLETE status but its
recorded evidence shows failing or absent tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from hook_utils import allow, block, read_event

READY_MARKERS = ("READY", "COMPLETE", "PRODUCTION_READY", "PUBLIC_BETA_READY")


def _repo_root(event: dict) -> Path:
    cwd = event.get("cwd") or event.get("project_dir")
    return Path(cwd) if cwd else Path.cwd()


def main() -> None:
    event = read_event()
    state_file = _repo_root(event) / "LOOP_STATE.json"
    if not state_file.exists():
        allow()  # nothing to contradict

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        allow()  # unparseable -> don't trap; a human will notice

    status = str(state.get("status", "")).upper()
    if not any(m in status for m in READY_MARKERS):
        allow()  # not claiming readiness -> fine

    results = state.get("last_test_results") or {}
    result_text = str(results.get("result", "")).lower()
    passed = "pass" in result_text and "fail" not in result_text
    if not passed:
        block(
            "[stop_gate] BLOCKED: LOOP_STATE.json status claims readiness "
            f"('{status}') but last_test_results does not show passing tests "
            f"({results.get('result', '<none>')!r}). Re-run the suite and record "
            "current evidence before finishing."
        )
    allow()


if __name__ == "__main__":
    main()
