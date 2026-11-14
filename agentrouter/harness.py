"""Introspective harness detection (Production Milestone 1).

Distinct from `hosts.py`, which answers "can AgentRouter dispatch a task to
Claude Code / Codex / etc" (prospective, evidence about the *target*). This
module answers "is *this* agentrouter process itself running inside one of
those tools right now" (introspective, evidence about the *caller*) — useful
for pre-flight context and support requests.

Detection is evidence-only and conservative. A named harness is reported only
from a variable that tool sets for itself and that this project has verified
first-hand; every other case reports GENERIC or UNKNOWN rather than guessing
from a weak, unrelated signal. Today that means Claude Code (CLAUDECODE,
verified: this project's own sessions run with it set) and the two
industry-standard CI variables (CI, GITHUB_ACTIONS). Codex, Cursor, and
similar tools are not yet detected — see integrations/README.md, which
integrates them as pasted instructions with no runtime footprint to detect.
Add a case here only once real evidence (a variable that tool documents or
that this project has observed directly) is available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

CLAUDE_CODE = "claude-code"
CI_GITHUB_ACTIONS = "ci-github-actions"
CI_GENERIC = "ci-generic"
GENERIC = "generic"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class HarnessInfo:
    name: str
    evidence: str


def detect_harness(env: dict[str, str] | None = None) -> HarnessInfo:
    """Best-effort, evidence-based harness identity. Never raises."""
    e = os.environ if env is None else env
    if e.get("CLAUDECODE"):
        return HarnessInfo(CLAUDE_CODE, "CLAUDECODE env var is set")
    if e.get("GITHUB_ACTIONS") == "true":
        return HarnessInfo(CI_GITHUB_ACTIONS, "GITHUB_ACTIONS=true")
    if e.get("CI") == "true":
        return HarnessInfo(CI_GENERIC, "CI=true")
    if e.get("TERM") or e.get("SHELL"):
        return HarnessInfo(GENERIC, "interactive shell evidence, no known-tool marker")
    return HarnessInfo(UNKNOWN, "no harness evidence found")
