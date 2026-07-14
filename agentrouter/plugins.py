"""Plugin/skill installer (Phase P8).

Installs AgentRouter's host integrations (Claude Code skill, Codex AGENTS.md)
from bundled package data into the host's config directory. Installation is:

- **reversible** — overwritten user files are backed up to ``<file>.agentrouter-bak``
  and restored on uninstall; files we created are removed;
- **idempotent** — a dest already identical to the source is skipped;
- **explicit** — ``plan()`` lists every file that would change before it changes;
- **safe** — an existing *different* user file is never overwritten without
  ``force`` (and then only after a backup).

Default destination roots live under the user's home. Tests (and power users)
override the base with ``AGENTROUTER_PLUGIN_ROOT``; each plugin then installs
under ``<root>/<plugin-name>``.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_BAK_SUFFIX = ".agentrouter-bak"


@dataclass(frozen=True)
class PluginFile:
    src: str  # path under agentrouter/integrations/
    dest: str  # path relative to the plugin's destination root


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    files: tuple[PluginFile, ...]
    _home_subdir: str  # default root relative to Path.home()


PLUGINS: dict[str, Plugin] = {
    "claude-code": Plugin(
        name="claude-code",
        description="AgentRouter routing skill for Claude Code (~/.claude/skills/agentrouter/).",
        files=(PluginFile("claude-code/agentrouter/SKILL.md", "skills/agentrouter/SKILL.md"),),
        _home_subdir=".claude",
    ),
    "codex": Plugin(
        name="codex",
        description="AgentRouter AGENTS.md guidance for Codex (~/.codex/AGENTS.md).",
        files=(PluginFile("codex/AGENTS.md", "AGENTS.md"),),
        _home_subdir=".codex",
    ),
}


class PluginError(Exception):
    """Raised for unknown plugins or unsafe install conditions."""


def get_plugin(name: str) -> Plugin:
    try:
        return PLUGINS[name]
    except KeyError:
        raise PluginError(f"unknown plugin '{name}'. Known: {', '.join(sorted(PLUGINS))}") from None


def dest_root(p: Plugin) -> Path:
    override = os.environ.get("AGENTROUTER_PLUGIN_ROOT")
    if override:
        return Path(override) / p.name
    return Path.home() / p._home_subdir


def _src_text(rel: str) -> str:
    base = resources.files("agentrouter") / "integrations"
    return (base / rel).read_text(encoding="utf-8")


def plan(p: Plugin) -> list[dict]:
    """What install would do to each file, without changing anything."""
    root = dest_root(p)
    out: list[dict] = []
    for f in p.files:
        dest = root / f.dest
        want = _src_text(f.src)
        if not dest.exists():
            action = "create"
        elif dest.read_text(encoding="utf-8") == want:
            action = "skip (identical)"
        else:
            action = "overwrite (backup first)"
        out.append({"dest": str(dest), "action": action})
    return out


def status(p: Plugin) -> str:
    root = dest_root(p)
    present = [(root / f.dest).exists() for f in p.files]
    if all(present):
        return "installed"
    if any(present):
        return "partial"
    return "not-installed"


def install(p: Plugin, force: bool = False) -> list[dict]:
    """Copy bundled files into the destination root; returns per-file results."""
    root = dest_root(p)
    results: list[dict] = []
    for f in p.files:
        dest = root / f.dest
        want = _src_text(f.src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            current = dest.read_text(encoding="utf-8")
            if current == want:
                results.append({"dest": str(dest), "result": "skipped (identical)"})
                continue
            if not force:
                raise PluginError(
                    f"{dest} exists and differs; re-run with --force to back it up and replace."
                )
            backup = dest.with_name(dest.name + _BAK_SUFFIX)
            shutil.copyfile(dest, backup)
            dest.write_text(want, encoding="utf-8")
            results.append({"dest": str(dest), "result": f"replaced (backup: {backup.name})"})
        else:
            dest.write_text(want, encoding="utf-8")
            results.append({"dest": str(dest), "result": "created"})
    return results


def uninstall(p: Plugin) -> list[dict]:
    """Remove installed files; restore a backup if one exists."""
    root = dest_root(p)
    results: list[dict] = []
    for f in p.files:
        dest = root / f.dest
        backup = dest.with_name(dest.name + _BAK_SUFFIX)
        if not dest.exists():
            results.append({"dest": str(dest), "result": "absent"})
            continue
        dest.unlink()
        if backup.exists():
            shutil.copyfile(backup, dest)
            backup.unlink()
            results.append({"dest": str(dest), "result": "removed (restored backup)"})
        else:
            results.append({"dest": str(dest), "result": "removed"})
    return results
