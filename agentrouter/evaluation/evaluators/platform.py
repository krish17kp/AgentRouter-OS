"""CLI platform evaluator (§7 cli_platform, weight 10).

Programmatic (no shelling out): imports the Typer app and confirms the expected
commands and command groups are registered. Score = fraction of expected
commands + groups present. Importing ``app`` at module load also proves the CLI
module and its transitive imports are healthy.
"""

from __future__ import annotations

from agentrouter.cli import app

# The user-facing surface the program promises (program §CLI_SPEC).
_EXPECTED_COMMANDS = {
    "init",
    "setup",
    "route",
    "explain",
    "feedback",
    "execute",
    "stats",
    "dashboard",
    "evaluate",
}
_EXPECTED_GROUPS = {"registry", "providers", "prompt", "hosts", "models", "plugin", "eval"}


def _command_names() -> set[str]:
    names: set[str] = set()
    for c in app.registered_commands:
        name = c.name or (c.callback.__name__.replace("_", "-") if c.callback else None)
        if name:
            names.add(name)
    return names


def _group_names() -> set[str]:
    return {g.name for g in app.registered_groups if g.name}


def evaluate_platform() -> dict:
    """Fraction of expected CLI commands + groups that are actually registered."""
    commands = _command_names()
    groups = _group_names()
    expected = _EXPECTED_COMMANDS | _EXPECTED_GROUPS
    present = (_EXPECTED_COMMANDS & commands) | (_EXPECTED_GROUPS & groups)
    missing = sorted(expected - present)
    score = len(present) / len(expected) if expected else 0.0
    return {
        "score": round(score, 4),
        "detail": {
            "expected": len(expected),
            "present": len(present),
            "missing": missing,
            "commands_found": sorted(commands),
            "groups_found": sorted(groups),
        },
    }
