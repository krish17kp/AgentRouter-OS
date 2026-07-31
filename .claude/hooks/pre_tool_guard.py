#!/usr/bin/env python3
"""PreToolUse guard for AgentRouter OS.

Blocks irreversible / policy-violating Bash commands per command.md section 1 & 6:
git write ops, destructive resets/deletes, DB destruction, deployment, secret
printing, shell=True, permission bypass, and package publication.

Exit 2 blocks the call. Everything else is allowed. Fails OPEN on parse errors
(a malformed event must not wedge the session) but logs to stderr.
"""

from __future__ import annotations

import re

from hook_utils import allow, bash_command, block, read_event

# (compiled pattern, human reason). Ordered; first match wins.
BLOCKED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgit\s+push\b"), "git push is forbidden (command.md)."),
    (re.compile(r"\bgit\s+commit\b"), "git commit is forbidden (command.md)."),
    (re.compile(r"\bgit\s+add\b"), "git add is forbidden (command.md)."),
    (re.compile(r"\bgit\s+tag\b"), "git tag is forbidden (command.md)."),
    (
        re.compile(r"\bgit\s+(rebase|reflog\s+expire|filter-branch)\b"),
        "git history rewrite is forbidden (command.md).",
    ),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "destructive git reset --hard is forbidden."),
    (
        re.compile(r"\bgit\s+(push|checkout)\b.*--force|\s-f\b.*\bgit\s+push"),
        "force push is forbidden.",
    ),
    (
        re.compile(r"\brm\s+-rf?\b.*(/|\\|\.\.|data|\.git|\*)"),
        "recursive delete of repo/data is forbidden.",
    ),
    (
        re.compile(r"\b(DROP|TRUNCATE|DELETE)\s+(TABLE|DATABASE|FROM)\b", re.I),
        "destructive database operation is forbidden.",
    ),
    (
        re.compile(
            r"\b(railway\s+up|railway\s+deploy|vercel\s+deploy|"
            r"vercel\s+--prod|netlify\s+deploy|fly\s+deploy|kubectl\s+(apply|delete))\b",
            re.I,
        ),
        "production deployment is forbidden (P11 owner-only).",
    ),
    (
        re.compile(
            r"(twine\s+upload|python\s+-m\s+twine\s+upload|npm\s+publish|"
            r"poetry\s+publish|flit\s+publish)",
            re.I,
        ),
        "package publication is forbidden (marketplace = owner-only).",
    ),
    (re.compile(r"shell\s*=\s*True"), "subprocess shell=True is forbidden (command.md)."),
    (
        re.compile(r"--dangerously-skip-permissions"),
        "--dangerously-skip-permissions is forbidden (command.md).",
    ),
    # Secret exposure: printing common key vars or .env contents.
    (
        re.compile(
            r"\b(echo|printenv|cat|type|Get-Content)\b.*"
            r"(API_KEY|SECRET|TOKEN|PASSWORD|\.env\b)",
            re.I,
        ),
        "printing secrets / .env contents is forbidden (command.md).",
    ),
]


def main() -> None:
    event = read_event()
    cmd = bash_command(event)
    if not cmd:
        allow()
    for pattern, reason in BLOCKED:
        if pattern.search(cmd):
            block(f"[pre_tool_guard] BLOCKED: {reason}\n  command: {cmd[:200]}")
    allow()


if __name__ == "__main__":
    main()
