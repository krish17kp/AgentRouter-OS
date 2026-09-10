#!/usr/bin/env python3
"""PreToolUse guard for AgentRouter OS.

Blocks irreversible / policy-violating Bash commands per command.md §14
("AUTONOMY AND SAFETY") and the AGENTS.md "Git and autonomy policy".

Git write policy (owner-authorized 2026-08-08). The previous revision blocked
`git add`/`git commit`/`git push` unconditionally, which contradicted both
command.md §14 ("You may: ... commit verified work; push to the current
release/task branch") and AGENTS.md, and made the documented per-task loop
impossible to execute. The rule is now branch-aware rather than absolute:

  * `git add` / `git commit` — allowed ONLY while on a `task/*` branch.
  * `git push`              — allowed ONLY from a `task/*` branch, only for
                              that same branch (`-u`/`--set-upstream` fine),
                              never forced, never targeting a protected branch.
  * `main` and `release/*`  — every git write is refused. The RC advances
                              through reviewed PR merges, never direct writes.

Everything previously blocked stays blocked: force push, remote-branch
deletion, tags, history rewriting (`rebase`/`filter-branch`/`reflog expire`),
`reset --hard`, `git clean`, recursive deletes, DB destruction, deployment,
package publication, `shell=True`, permission bypass and secret printing.

Exit 2 blocks the call. Everything else is allowed. Fails OPEN on parse errors
(a malformed event must not wedge the session) but logs to stderr.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess

from hook_utils import allow, bash_command, block, read_event

# Branches that never accept a direct git write. A detached HEAD is not listed
# here on purpose: `git rev-parse --abbrev-ref HEAD` reports "HEAD" when
# detached, which fails the task/* prefix rule anyway, whereas "HEAD" used as a
# push *destination* is the ordinary way to name the current branch.
PROTECTED_BRANCHES = frozenset({"main", "master"})
PROTECTED_PREFIXES = ("release/",)
# Only these branches may be written to / pushed.
TASK_PREFIX = "task/"

# Git subcommands gated on being at work on a task branch.
_WRITE_SUBCOMMANDS = frozenset({"add", "commit"})

# (compiled pattern, human reason). Ordered; first match wins. These are
# unconditional — no branch makes them acceptable.
BLOCKED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgit\s+tag\b"), "git tag is forbidden (owner-only release step)."),
    (
        re.compile(r"\bgit\s+(rebase|reflog\s+expire|filter-branch)\b"),
        "git history rewrite is forbidden (command.md).",
    ),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "destructive git reset --hard is forbidden."),
    (re.compile(r"\bgit\s+clean\b"), "git clean is forbidden (AGENTS.md: never discard work)."),
    (re.compile(r"\bgit\s+checkout\b[^|;&]*--force\b"), "force checkout is forbidden."),
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


def _is_protected(branch: str) -> bool:
    """True for a branch that must never take a direct git write."""
    return branch in PROTECTED_BRANCHES or branch.startswith(PROTECTED_PREFIXES)


def _current_branch(event: dict) -> str:
    """Best-effort current branch in the tool call's cwd; '' if undeterminable."""
    cwd = event.get("cwd") or os.getcwd()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _segments(cmd: str) -> list[str]:
    """Split a compound command into independently-evaluated pieces."""
    return [s for s in re.split(r"&&|\|\||;|\||\n", cmd) if s.strip()]


# Shell redirections (`2>&1`, `> out.txt`, `>>log`, `2> /dev/null`) are not
# arguments to the command and must never be mistaken for a push refspec.
_REDIRECT_RE = re.compile(r"(?:\d?>>?|\d?<|&>)\s*(?:&\d+|\S+)?")


def _tokens(segment: str) -> list[str]:
    segment = _REDIRECT_RE.sub(" ", segment)
    try:
        return shlex.split(segment)
    except ValueError:  # unbalanced quotes (heredoc fragment, etc.)
        return segment.split()


def _git_tail(tokens: list[str]) -> list[str] | None:
    """Tokens starting at the git subcommand, or None if this isn't a git call."""
    try:
        i = tokens.index("git")
    except ValueError:
        return None
    i += 1
    # skip git's own options (`-C <path>`, `-c k=v`, `--no-pager`, …)
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] in ("-C", "-c"):
            i += 1
        i += 1
    return tokens[i:] if i < len(tokens) else None


def _is_force(tokens: list[str]) -> bool:
    for t in tokens:
        if t == "--force" or t.startswith(("--force-with-lease", "--force-if-includes")):
            return True
        # bundled short flags such as -f or -uf
        if re.fullmatch(r"-[a-zA-Z]+", t) and "f" in t:
            return True
    return False


def _push_positionals(tail: list[str]) -> list[str]:
    """Positional args after `push`, skipping flags and their values."""
    out: list[str] = []
    i = 1  # tail[0] == "push"
    while i < len(tail):
        t = tail[i]
        if t.startswith("-"):
            if t in ("-o", "--push-option", "--repo", "--exec", "--receive-pack"):
                i += 1  # this flag takes a separate value
        else:
            out.append(t)
        i += 1
    return out


def _check_push(tail: list[str], branch: str) -> str | None:
    if _is_force(tail):
        return "force push is forbidden."
    flags = {t for t in tail if t.startswith("-")}
    if flags & {"--delete", "-d"}:
        return "deleting a remote branch via git push is forbidden."
    if flags & {"--mirror", "--all", "--tags", "--follow-tags"}:
        return "bulk/tag push (--mirror/--all/--tags) is forbidden."
    if not branch:
        return "cannot determine the current branch; refusing git push."
    if not branch.startswith(TASK_PREFIX):
        return (
            f"git push is only authorized from a {TASK_PREFIX}* branch "
            f"(current branch: '{branch}'). The RC advances via reviewed PR merges."
        )
    # `git push [remote] [refspec...]` — the first positional is the remote.
    for spec in _push_positionals(tail)[1:]:
        dst = spec.split(":")[-1]
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/") :]
        if _is_protected(dst):
            return f"pushing to protected branch '{dst}' is forbidden."
        if dst not in (branch, "HEAD"):
            return f"push refspec '{spec}' does not match the current task branch '{branch}'."
    return None


def _check_git(cmd: str, event: dict) -> str | None:
    """Branch-aware policy for git write subcommands. None = allowed."""
    branch: str | None = None
    for segment in _segments(cmd):
        tail = _git_tail(_tokens(segment))
        if not tail:
            continue
        sub = tail[0]
        if sub not in _WRITE_SUBCOMMANDS and sub != "push":
            continue
        if branch is None:  # resolve lazily, at most once
            branch = _current_branch(event)
        if sub == "push":
            reason = _check_push(tail, branch)
            if reason:
                return reason
            continue
        if _is_protected(branch):
            return (
                f"git {sub} on protected branch '{branch}' is forbidden. "
                f"Create a {TASK_PREFIX}* branch first."
            )
        if not branch.startswith(TASK_PREFIX):
            return (
                f"git {sub} is only authorized on a {TASK_PREFIX}* branch "
                f"(current branch: '{branch or 'unknown'}')."
            )
    return None


def main() -> None:
    event = read_event()
    cmd = bash_command(event)
    if not cmd:
        allow()
    for pattern, reason in BLOCKED:
        if pattern.search(cmd):
            block(f"[pre_tool_guard] BLOCKED: {reason}\n  command: {cmd[:200]}")
    reason = _check_git(cmd, event)
    if reason:
        block(f"[pre_tool_guard] BLOCKED: {reason}\n  command: {cmd[:200]}")
    allow()


if __name__ == "__main__":
    main()
