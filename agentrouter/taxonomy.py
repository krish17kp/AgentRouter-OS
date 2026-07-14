"""Versioned tool/workload taxonomy (Phase P4).

A single canonical vocabulary for tool capabilities, shared by the classifier
(what a task *requires*), the model registry (what a model *supports*) and the
host layer. Backward compatible: the legacy labels ``web``, ``shell`` and
``file-edit`` remain canonical members, and equivalence groups let an old label
match a newer synonym (e.g. a task needing ``web`` is satisfied by a model that
lists ``web-search``).
"""

from __future__ import annotations

TAXONOMY_VERSION = "1"

# Canonical capability labels (command.md P4).
TOOLS: frozenset[str] = frozenset(
    {
        "file-read",
        "file-edit",
        "shell",
        "code-execution",
        "browser-automation",
        "web-search",
        "network-http",
        "database-read",
        "database-write",
        "cloud-read",
        "cloud-write",
        "git-read",
        "git-write",
        "issue-tracker",
        "vision",
        "audio",
        "structured-output",
        "function-calling",
        "long-running-agent",
        "parallel-subagents",
        # legacy-but-canonical: kept so existing registries/classifier stay valid
        "web",
        "tool-use",
    }
)

# Bidirectional equivalence groups: any member satisfies a requirement for any
# other member. Conservative on purpose — only genuine synonyms.
_EQUIV_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"web", "web-search"}),
    frozenset({"tool-use", "function-calling"}),
)


def is_known(tool: str) -> bool:
    return tool in TOOLS


def equivalents(tool: str) -> frozenset[str]:
    """All labels that satisfy a requirement for ``tool`` (including itself)."""
    for group in _EQUIV_GROUPS:
        if tool in group:
            return group
    return frozenset({tool})


def satisfied_by(required: str, supported: set[str]) -> bool:
    """True if a model/host offering ``supported`` covers the ``required`` tool."""
    return bool(equivalents(required) & supported)
