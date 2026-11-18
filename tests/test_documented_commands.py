"""Commands shown to users must exist (TASK-019).

Writing the plugin section of `USER_GUIDE.md` I documented three things that were
not real: a `plugin status` subcommand, an `--apply` flag on `install` (it
applies by default and takes `--dry-run`), and an `--apply` on `uninstall` (which
takes no flags at all). Every one of them read plausibly. Prose is not executed,
so nothing would have failed until a user typed it.

These tests parse the command lines out of the user-facing docs and check each
one against the real Typer app, so a renamed subcommand or a dropped flag breaks
the build instead of the reader.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.main import get_command

from agentrouter.cli import app

REPO = Path(__file__).resolve().parents[1]
DOCS = ("USER_GUIDE.md", "docs/RUNBOOKS.md", "CLI_SPEC.md")

# `$ agentrouter plugin install claude-code --dry-run` -> the words after the name.
_INVOCATION = re.compile(r"agentrouter ((?:[a-z][a-z0-9-]*\s*)+(?:--[a-z][a-z0-9-]*\s*)*)")


def _documented() -> set[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()
    for name in DOCS:
        path = REPO / name
        if not path.exists():
            continue
        for raw in _INVOCATION.findall(path.read_text(encoding="utf-8")):
            words = tuple(raw.split())
            if words:
                found.add(words)
    return found


def _resolve(words: tuple[str, ...]):
    """Walk the click command tree; return (command, leftover words) or None."""
    command = get_command(app)
    index = 0
    while index < len(words) and hasattr(command, "commands"):
        child = command.commands.get(words[index])
        if child is None:
            break
        command = child
        index += 1
    return command, words[index:]


@pytest.mark.parametrize("words", sorted(_documented()))
def test_a_documented_invocation_names_a_real_command_and_flags(words):
    command, rest = _resolve(words)

    # Bare leftover words are argument values (`explain <id>`), which cannot be
    # validated from prose. Flags can be, and are the half that silently rots.
    flags = {opt for param in command.params for opt in param.opts if opt.startswith("--")}
    documented_flags = {w for w in rest if w.startswith("--")}
    unknown = sorted(f for f in documented_flags if f not in flags)
    assert unknown == [], (
        f"docs show `agentrouter {' '.join(words)}` but {command.name} has no {unknown}"
    )


def test_the_plugin_subcommands_the_guide_lists_all_exist():
    """The specific regression: three invented plugin commands shipped in prose."""
    plugin = get_command(app).commands["plugin"]
    guide = (REPO / "USER_GUIDE.md").read_text(encoding="utf-8")

    used = set(re.findall(r"agentrouter plugin ([a-z][a-z0-9-]*)", guide))
    assert used, "the guide documents no plugin subcommands"
    missing = sorted(name for name in used if name not in plugin.commands)
    assert missing == [], f"USER_GUIDE.md documents plugin subcommands that do not exist: {missing}"
