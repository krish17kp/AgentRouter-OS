"""Rule-based TaskClassifier — 7 dimensions per ROUTING_RULES.md §1 (MVP heuristics)."""

from __future__ import annotations

import re

from .schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    OutputType,
    TaskType,
)

# --- signal word sets (heuristic, MVP) --------------------------------------

_SUMMARIZE = ("summarize", "summary", "tl;dr", "tldr", "condense", "into bullets")
# Documentation intent — checked BEFORE coding so "Python/CLI/repo/project" mentions
# never override README/docs intent. Artifact nouns + doc-editing verbs.
_DOC_ARTIFACTS = (
    "readme", "prd", "brd", "roadmap", "milestone", "user guide", "changelog",
    "documentation", "docs", "architecture doc", "design doc", "overview",
    "report", "guide", "wiki", "tutorial",
)
_DOC_VERBS = ("polish", "rewrite", "proofread", "explain")
_CODING = (
    "refactor", "debug", "implement", "fix", "bug", "code", "script", "function",
    "endpoint", "unit test", "compile", "regex", "sql", "api", "class", "module",
    "one-liner", "bash", "python", "typescript", "command", "cli",
)
_WRITING = ("write a blog", "write an article", "write documentation", "draft", "email", "essay", "readme")
_ANALYSIS = ("analyze", "analyse", "compare", "review", "evaluate", "assess", "what's wrong", "describe")
_REASONING = ("plan", "design", "architect", "prove", "solve", "strategy", "decide")

_RISK_HIGH = (  # "token" deliberately absent: collides with LLM-token phrasing
    "auth", "password", "secret", "credential", "api key", "payment", "billing",
    "production", "prod ", "delete", "drop table", "migration", "migrate",
    "infrastructure", "terraform", "kubernetes", "deploy",
)
_RISK_MEDIUM = ("database", "config", "user data", "pii", "schema", "env var")

_TRIVIAL = ("one-liner", "oneliner", "simple", "quick", "small", "trivial", "single line")
_COMPLEX = ("refactor", "redesign", "overhaul", "architecture", "end-to-end", "entire", "across", "migrate")

_FILE_EDIT = ("refactor", "edit", "modify", "rename", "update the", "codebase", "our ", "module", "add tests")
_SHELL = ("run", "execute", "install", "build", "test")
_VISION = ("image", "screenshot", "photo", "diagram", "mockup", "picture")
_WEB = ("search the web", "browse", "latest news", "look up online")

_TOKEN_RE = re.compile(r"(\d+)\s*k[\s-]*token", re.IGNORECASE)
_TOKEN_PLAIN_RE = re.compile(r"(\d{4,})[\s-]*token", re.IGNORECASE)


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _is_documentation(text: str) -> bool:
    """Doc-artifact nouns or doc-editing verbs signal writing, not coding.

    'docstring' is excluded: adding docstrings is a coding task, not docs.
    """
    text = text.replace("docstring", "")
    return _contains(text, _DOC_ARTIFACTS) or _contains(text, _DOC_VERBS)


def _task_type(text: str) -> TaskType:
    if _contains(text, _SUMMARIZE):
        return TaskType.summarization
    if _is_documentation(text):  # before coding: "Python CLI project" must not override README intent
        return TaskType.writing
    if _contains(text, _CODING):
        return TaskType.coding
    if _contains(text, _WRITING):
        return TaskType.writing
    if _contains(text, _ANALYSIS):
        return TaskType.analysis
    if _contains(text, _REASONING):
        return TaskType.reasoning
    return TaskType.general


def _risk(text: str) -> Level:
    if _contains(text, _RISK_HIGH):
        return Level.high
    if _contains(text, _RISK_MEDIUM):
        return Level.medium
    return Level.low


def _complexity(text: str, task_type: TaskType) -> Level:
    if _contains(text, _TRIVIAL):
        return Level.low
    signals = 0
    if _contains(text, _COMPLEX):
        signals += 1
    if text.count(" and ") >= 1 and task_type is TaskType.coding:
        signals += 1  # chained subtasks
    if len(text.split()) > 25:
        signals += 1
    if signals >= 2:
        return Level.high
    if signals == 1:
        return Level.medium
    return Level.low


def _context_tokens(text: str) -> int:
    m = _TOKEN_RE.search(text)
    if m:
        return int(m.group(1)) * 1000
    m = _TOKEN_PLAIN_RE.search(text)
    if m:
        return int(m.group(1))
    if _contains(text, ("codebase", "repo", "module", "our ", "files", "project")):
        return 12000
    if _contains(text, ("document", "report", "filing", "book", "transcript")):
        return 30000
    return 2000


def _band(tokens: int) -> ContextBand:
    if tokens < 8_000:
        return ContextBand.small
    if tokens < 64_000:
        return ContextBand.medium
    return ContextBand.large


def _output_type(text: str, task_type: TaskType) -> OutputType:
    if task_type is TaskType.coding and "test" in text:
        return OutputType.code_tests
    if task_type is TaskType.coding:
        return OutputType.code
    if _contains(text, ("plan", "roadmap", "design doc")):
        return OutputType.plan
    if _contains(text, ("csv", "json", "table of", "spreadsheet")):
        return OutputType.data
    return OutputType.text


def _tool_needs(text: str, task_type: TaskType) -> list[str]:
    needs = []
    if task_type is TaskType.coding and _contains(text, _FILE_EDIT):
        needs.append("file-edit")
    if task_type is TaskType.coding and _contains(text, _SHELL):
        needs.append("shell")
    if _contains(text, _VISION):
        needs.append("vision")
    if _contains(text, _WEB):
        needs.append("web")
    return needs


_APPROVAL = {
    Level.low: ApprovalLevel.auto,
    Level.medium: ApprovalLevel.notify,
    Level.high: ApprovalLevel.human_approval_required,
}


def classify(
    task: str,
    *,
    context_tokens: int | None = None,
    risk: Level | None = None,
    tools: list[str] | None = None,
) -> Classification:
    """Classify a task; keyword overrides win over inference (CLI --risk/--tool/--context-tokens)."""
    text = task.lower()
    task_type = _task_type(text)
    resolved_risk = risk or _risk(text)
    tokens = context_tokens if context_tokens is not None else _context_tokens(text)
    return Classification(
        task_type=task_type,
        complexity=_complexity(text, task_type),
        risk=resolved_risk,
        context_tokens=tokens,
        context_band=_band(tokens),
        output_type=_output_type(text, task_type),
        tool_needs=tools if tools is not None else _tool_needs(text, task_type),
        approval_level=_APPROVAL[resolved_risk],
    )
