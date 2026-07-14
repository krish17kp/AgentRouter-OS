"""Rule-based TaskClassifier — 7 dimensions per ROUTING_RULES.md §1.

Matching is word-boundary (regex), not substring, so "rag" no longer fires on
"pa[rag]raph", "cli" on "de[cli]ning", or "sql" on "postgre[sql]". Task-type
precedence is deliberate and phrase-level (see `_task_type`):

    summarization -> software-build -> documentation -> writing phrase ->
    component-coding -> analysis -> reasoning -> coding keyword -> general

Software-build runs before documentation so "build a sales guide app" is coding
(the artifact noun wins) while "write a sales guide" stays writing. A build/edit
verb applied to a named software component ("add validation to the signup form")
reads as coding even with no bare coding keyword.
"""

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


def _matcher(words: tuple[str, ...]) -> re.Pattern:
    """Compile a word-boundary alternation over the given tokens/phrases."""
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


# --- signal vocabularies (matched at word boundaries) -----------------------

M_SUMMARIZE = _matcher(
    (
        "summarize",
        "summarise",
        "summary",
        "summriz",
        "tl;dr",
        "tldr",
        "condense",
        "recap",
        "abstract of",
    )
)
# Doc artifacts kept deliberately unambiguous — "report"/"overview" removed
# because "review the incident report" is analysis, not writing.
M_DOC_ARTIFACTS = _matcher(
    (
        "readme",
        "prd",
        "brd",
        "roadmap",
        "changelog",
        "documentation",
        "docs",
        "design doc",
        "architecture doc",
        "wiki",
        "tutorial",
        "user guide",
    )
)
M_DOC_VERBS = _matcher(("polish", "rewrite", "proofread", "proof-read"))

# Strong writing phrases — checked before component-coding so "write a blog
# post about our API launch" is writing, not coding.
M_WRITING = _matcher(
    (
        "write a blog",
        "write an article",
        "blog post",
        "article",
        "draft",
        "email",
        "essay",
        "cover letter",
        "tweet",
        "newsletter",
        "marketing copy",
        "landing page headline",
        "short story",
        "release notes",
        "proposal",
        "paragraph",
        "press release",
        "announcement",
        "guide",
        "sales guide",
    )
)

# Build/scaffold verbs (paired with a software noun => coding).
M_BUILD_VERBS = _matcher(
    (
        "build",
        "create",
        "develop",
        "implement",
        "scaffold",
        "set up",
        "stand up",
        "spin up",
        "make a",
        "make an",
    )
)
# Project-level nouns imply file editing AND a run/build step.
_PROJECT_NOUNS = (
    "app",
    "apps",
    "application",
    "service",
    "microservice",
    "system",
    "website",
    "web app",
    "platform",
    "cli",
    "cli tool",
    "pipeline",
    "bot",
    "extension",
    "backend",
    "frontend",
    "mvp",
    "prototype",
    "dashboard",
    "server",
)
# Component-level nouns imply file editing but not necessarily a run step.
# "function"/"class" are intentionally absent: they are snippet-level (a bare
# "binary search function" needs no file edit), and live in M_SNIPPET instead.
_COMPONENT_NOUNS = (
    "handler",
    "endpoint",
    "endpoints",
    "middleware",
    "component",
    "module",
    "controller",
    "model",
    "schema",
    "route",
    "form",
    "worker",
    "package",
    "api",
    "database",
    "table",
    "page",
    "toggle",
    "widget",
    "feature",
    "webhook",
    "parser",
    "job",
    "layer",
    "script",
    "code",
)
M_PROJECT_NOUNS = _matcher(_PROJECT_NOUNS)
M_COMPONENT_NOUNS = _matcher(_PROJECT_NOUNS + _COMPONENT_NOUNS)
M_SOFTWARE_DOMAIN = _matcher(
    (
        "rag",
        "retrieval",
        "embedding",
        "embeddings",
        "vector database",
        "vector store",
        "vector db",
        "vector search",
        "chunking",
        "ingestion",
        "etl",
        "fine-tune",
        "fine tune",
        "inference pipeline",
    )
)

# Action verbs that, applied to a named component, make a task coding.
M_ACTION_VERBS = _matcher(
    (
        "write",
        "create",
        "build",
        "develop",
        "implement",
        "add",
        "refactor",
        "fix",
        "modify",
        "update",
        "rename",
        "convert",
        "optimize",
        "optimise",
        "integrate",
        "configure",
        "scaffold",
        "patch",
        "wire",
        "store",
        "encrypt",
        "hash",
        "parse",
        "debug",
        "deploy",
        "provision",
        "install",
        "generate",
        "connect",
        "set up",
        "back up",
        "handle",
        "train",
    )
)

M_CODING = _matcher(
    (
        "refactor",
        "debug",
        "implement",
        "fix",
        "bug",
        "code",
        "script",
        "function",
        "endpoint",
        "unit test",
        "compile",
        "regex",
        "sql",
        "api",
        "class",
        "module",
        "one-liner",
        "bash",
        "python",
        "typescript",
        "command",
        "cli",
        "configure",
        "oauth",
        "oauth2",
        "integrate",
        "provision",
        "middleware",
        "webhook",
        "test",
        "tests",
        "hashing",
        "salting",
        "encrypt",
        "decrypt",
        "cache",
        "caching",
        "parser",
        "query",
        "database",
        "pipeline",
        "deploy",
        "deployment",
        "train",
        "rollback",
        "classifier",
        "docstring",
        "docstrings",
    )
)
M_ANALYSIS = _matcher(
    (
        "analyze",
        "analyse",
        "analysis",
        "compare",
        "review",
        "evaluate",
        "assess",
        "what's wrong",
        "whats wrong",
        "audit",
        "investigate",
        "root cause",
        "look into",
    )
)
M_REASONING = _matcher(
    (
        "plan",
        "design",
        "architect",
        "architecture",
        "prove",
        "solve",
        "strategy",
        "strategize",
        "decide",
        "devise",
        "figure out",
        "work out",
        "recommend",
    )
)

M_RISK_HIGH = _matcher(
    (
        "auth",
        "authentication",
        "authorization",
        "authorize",
        "password",
        "passwords",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "api key",
        "api keys",
        "payment",
        "payments",
        "billing",
        "production",
        "prod",
        "delete",
        "drop table",
        "migrate",
        "migration",
        "migrations",
        "terraform",
        "kubernetes",
        "deploy",
        "deployment",
        "oauth",
        "oauth2",
        "injection",
        "vulnerable",
        "vulnerability",
        "vulnerabilities",
        "encrypt",
        "encryption",
        "exploit",
        "cve",
        "pii",
        "rotate",
        "hashing",
        "salting",
    )
)
M_RISK_MEDIUM = _matcher(
    (
        "database",
        "config",
        "configuration",
        "user data",
        "schema",
        "env var",
        "upgrade",
        "dependency",
        "dependencies",
        "validation",
        "webhook",
        "rate limit",
        "rate limiting",
        "security",
        "permission",
        "permissions",
    )
)

M_TRIVIAL = _matcher(("one-liner", "oneliner", "single line", "trivial"))
M_COMPLEX = _matcher(
    (
        "refactor",
        "redesign",
        "overhaul",
        "architecture",
        "architect",
        "end-to-end",
        "entire",
        "across",
        "migrate",
        "migration",
        "multi-tenant",
        "scalable",
        "distributed",
        "real-time",
        "zero-downtime",
        "event-driven",
    )
)

M_SNIPPET = _matcher(
    ("function", "regex", "one-liner", "oneliner", "snippet", "algorithm", "query")
)
# Bare "image"/"the image" excluded: "the image processing worker" is not a
# vision task. Only explicit visual-input phrases count.
M_VISION = _matcher(("screenshot", "photo", "diagram", "mockup", "picture", "image of"))
M_WEB = _matcher(
    ("search the web", "browse", "latest news", "look up online", "google for", "web search")
)
_SHELL_WB = re.compile(
    r"\b(run|runs|execute|install|build|rebuild|deploy|provision|compile|test|"
    r"tests|migrate|rollback|roll back|back up|backup|apply|rename|train|ingest|"
    r"stand up|spin up|set up)\b",
    re.IGNORECASE,
)

_TEST_RE = re.compile(r"\btests?\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"(\d+)\s*k[\s-]*token", re.IGNORECASE)
_TOKEN_PLAIN_RE = re.compile(r"(\d{4,})[\s-]*token", re.IGNORECASE)


def _hit(rx: re.Pattern, text: str) -> bool:
    return rx.search(text) is not None


def _is_documentation(text: str) -> bool:
    """Doc-artifact nouns or doc-editing verbs => writing (docstring excluded)."""
    text = text.replace("docstring", "")
    return _hit(M_DOC_ARTIFACTS, text) or _hit(M_DOC_VERBS, text)


def _is_software_build(text: str) -> bool:
    """Build/scaffold verb + software noun, or a software-domain term."""
    if _hit(M_SOFTWARE_DOMAIN, text):
        return True
    return _hit(M_BUILD_VERBS, text) and _hit(M_COMPONENT_NOUNS, text)


def _has_component(text: str) -> bool:
    return _hit(M_COMPONENT_NOUNS, text)


def _is_component_coding(text: str) -> bool:
    """An action verb applied to a named software component => coding."""
    return _hit(M_ACTION_VERBS, text) and _has_component(text)


def _task_type(text: str, is_build: bool) -> TaskType:
    if _hit(M_SUMMARIZE, text):
        return TaskType.summarization
    if is_build:  # artifact noun beats a doc word like "guide"
        return TaskType.coding
    if _is_documentation(text):
        return TaskType.writing
    if _hit(M_WRITING, text):
        return TaskType.writing
    if _is_component_coding(text):
        return TaskType.coding
    if _hit(M_ANALYSIS, text):
        return TaskType.analysis
    if _hit(M_REASONING, text):
        return TaskType.reasoning
    if _hit(M_CODING, text):
        return TaskType.coding
    return TaskType.general


def _risk(text: str) -> Level:
    if _hit(M_RISK_HIGH, text):
        return Level.high
    if _hit(M_RISK_MEDIUM, text):
        return Level.medium
    return Level.low


def _complexity(text: str, task_type: TaskType, is_build: bool) -> Level:
    if _hit(M_TRIVIAL, text):
        return Level.low
    words = len(text.split())
    complex_hits = len(M_COMPLEX.findall(text))
    signals = 0
    if complex_hits >= 1:
        signals += 1
    if complex_hits >= 2:  # several complexity markers -> genuinely hard
        signals += 1
    if is_build:
        signals += 1
    if " and " in text and task_type is TaskType.coding:
        signals += 1
    if words > 25:
        signals += 1
    if len(M_SOFTWARE_DOMAIN.findall(text)) >= 2:
        signals += 1
    # design/architecture/analysis of a substantive object is at least medium
    if task_type is TaskType.reasoning and words >= 6:
        signals += 1
    if task_type is TaskType.analysis and words >= 7:
        signals += 1
    if signals >= 2:
        return Level.high
    if signals == 1:
        return Level.medium
    return Level.low


# Acting on an existing named software component (or reviewing existing work)
# means the model must load surrounding code/context — realistically medium,
# not a 2k-token snippet. "build a new X" stays small (handled by precedence).
M_EXISTING_CODE = _matcher(
    (
        "codebase",
        "repo",
        "repository",
        "module",
        "files",
        "project",
        "system",
        "endpoint",
        "endpoints",
        "package",
        "service",
        "microservice",
        "middleware",
        "controller",
        "handler",
        "webhook",
        "worker",
        "parser",
        "api",
        "migration",
        "pull request",
        "test coverage",
        "coverage",
        "the auth",
        "the payment",
    )
)


def _context_tokens(text: str) -> int:
    m = _TOKEN_RE.search(text)
    if m:
        return int(m.group(1)) * 1000
    m = _TOKEN_PLAIN_RE.search(text)
    if m:
        return int(m.group(1))
    if _hit(_matcher(("document", "report", "filing", "book", "transcript", "pdf")), text):
        return 30000
    if _hit(M_EXISTING_CODE, text):
        return 12000
    return 2000


def _band(tokens: int) -> ContextBand:
    if tokens < 8_000:
        return ContextBand.small
    if tokens < 64_000:
        return ContextBand.medium
    return ContextBand.large


def _output_type(text: str, task_type: TaskType) -> OutputType:
    if task_type is TaskType.coding and _TEST_RE.search(text):
        return OutputType.code_tests
    if task_type is TaskType.coding:
        return OutputType.code
    if _hit(_matcher(("csv", "json", "table of", "spreadsheet")), text):
        return OutputType.data
    if task_type is TaskType.reasoning or _hit(_matcher(("plan", "roadmap", "design doc")), text):
        return OutputType.plan
    return OutputType.text


def _is_pure_snippet(text: str, is_build: bool) -> bool:
    """A standalone function/regex/query with no named component to edit."""
    return _hit(M_SNIPPET, text) and not is_build and not _has_component(text)


def _tool_needs(text: str, task_type: TaskType, is_build: bool) -> list[str]:
    needs: list[str] = []
    if task_type is TaskType.coding:
        wants_edit = is_build or _has_component(text) or _hit(M_ACTION_VERBS, text)
        if wants_edit and not _is_pure_snippet(text, is_build):
            needs.append("file-edit")
        if _hit(M_PROJECT_NOUNS, text) or _SHELL_WB.search(text):
            needs.append("shell")
    if _hit(M_VISION, text):
        needs.append("vision")
    if _hit(M_WEB, text):
        needs.append("web")
    return needs


_APPROVAL = {
    Level.low: ApprovalLevel.auto,
    Level.medium: ApprovalLevel.notify,
    Level.high: ApprovalLevel.human_approval_required,
}

# Below this task-type confidence, route abstains (asks to clarify) rather than
# routing a vague/ambiguous request as if it were certain.
DEFAULT_UNCERTAINTY_THRESHOLD = 0.4


def _task_type_families(text: str, is_build: bool) -> list[TaskType]:
    """Which task-type families fired, in precedence order. Used for ambiguity."""
    fams: list[TaskType] = []
    if _hit(M_SUMMARIZE, text):
        fams.append(TaskType.summarization)
    if is_build or _is_component_coding(text) or _hit(M_CODING, text):
        fams.append(TaskType.coding)
    if _is_documentation(text) or _hit(M_WRITING, text):
        fams.append(TaskType.writing)
    if _hit(M_ANALYSIS, text):
        fams.append(TaskType.analysis)
    if _hit(M_REASONING, text):
        fams.append(TaskType.reasoning)
    return fams


def _confidence(
    text: str, task_type: TaskType, is_build: bool
) -> tuple[float, TaskType | None, str | None]:
    """Task-type interpretation confidence + optional runner-up and reason.

    Rule-based confidence: strong when exactly one task-type family matched and
    the task is not trivially short; weak when the classifier fell through to
    `general` or several competing families fired.
    """
    words = len(text.split())
    fams = _task_type_families(text, is_build)
    score = 0.5
    alternative: TaskType | None = None
    reason: str | None = None

    if task_type is TaskType.general and not fams:
        score = 0.25  # no signal fired — pure fallthrough
        reason = "no distinctive task signals matched"
    else:
        score += 0.3  # a specific rule matched

    distinct = [f for f in fams if f is not task_type]
    if not distinct and fams:
        score += 0.2  # single, unambiguous family
    elif distinct:
        score -= 0.15 * len(distinct)  # competing interpretations
        alternative = distinct[0]
        reason = f"also reads as {alternative.value}"

    if words < 3:
        score -= 0.25  # too terse to be sure
        reason = reason or "task description is very short"

    score = max(0.0, min(1.0, round(score, 2)))
    return score, alternative, reason


def classify(
    task: str,
    *,
    context_tokens: int | None = None,
    risk: Level | None = None,
    tools: list[str] | None = None,
    uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
) -> Classification:
    """Classify a task; explicit overrides (--risk/--tool/--context-tokens) win over inference."""
    text = task.lower()
    is_build = _is_software_build(text)
    task_type = _task_type(text, is_build)
    resolved_risk = risk or _risk(text)
    tokens = context_tokens if context_tokens is not None else _context_tokens(text)
    confidence, alternative, ambiguity = _confidence(text, task_type, is_build)
    return Classification(
        task_type=task_type,
        complexity=_complexity(text, task_type, is_build),
        risk=resolved_risk,
        context_tokens=tokens,
        context_band=_band(tokens),
        output_type=_output_type(text, task_type),
        tool_needs=tools if tools is not None else _tool_needs(text, task_type, is_build),
        approval_level=_APPROVAL[resolved_risk],
        confidence=confidence,
        needs_clarification=confidence < uncertainty_threshold,
        alternative_task_type=alternative,
        ambiguity_reason=ambiguity,
    )
