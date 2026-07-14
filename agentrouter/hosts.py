"""Execution-host discovery + two-stage host resolution (program Phase 4/5).

Stage 1 (engine) picks a MODEL. Stage 2 (here) picks HOW to run it: the best
available execution host among the model's execution_targets. Detection is
read-only and offline-safe:

- CLI hosts (claude-code, codex-cli): `shutil.which(required_command)`.
- API hosts (anthropic-api, openai-api, gemini-api, openrouter): the required
  env var is present (value never read/printed). This is availability, not a
  live connectivity check.
- manual: always available.

Availability is one of available | unavailable | unknown. `unknown` is never
promoted to `available`; default routing prefers models with an available host.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from .schema import ExecutionTarget, ModelEntry

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"

# static metadata for known hosts (kind + what makes them available)
_CLI_HOSTS = {"claude-code": "claude", "codex-cli": "codex"}
_API_HOSTS = {
    "anthropic-api": "ANTHROPIC_API_KEY",
    "openai-api": "OPENAI_API_KEY",
    "gemini-api": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class HostStatus:
    host: str
    availability: str
    reason: str


def detect_host(host: str, required_command: str | None = None) -> HostStatus:
    """Read-only availability check for one host. Never runs the tool or prints secrets."""
    if host == "manual":
        return HostStatus(host, AVAILABLE, "manual execution is always available")
    cmd = required_command or _CLI_HOSTS.get(host)
    if host in _CLI_HOSTS or (required_command and host not in _API_HOSTS):
        if cmd and shutil.which(cmd):
            return HostStatus(host, AVAILABLE, f"'{cmd}' found on PATH")
        return HostStatus(host, UNAVAILABLE, f"'{cmd}' not found on PATH")
    if host in _API_HOSTS:
        env = _API_HOSTS[host]
        if os.environ.get(env):
            return HostStatus(host, AVAILABLE, f"{env} is set")
        return HostStatus(host, UNAVAILABLE, f"{env} is not set")
    return HostStatus(host, UNKNOWN, "unrecognized host; cannot verify availability")


def target_status(t: ExecutionTarget) -> HostStatus:
    return detect_host(t.host, t.required_command)


@dataclass(frozen=True)
class ResolvedRoute:
    target: ExecutionTarget | None
    status: HostStatus | None
    all_statuses: list[HostStatus]

    @property
    def is_available(self) -> bool:
        return self.status is not None and self.status.availability == AVAILABLE


def resolve_execution_route(model: ModelEntry, include_unavailable: bool = False) -> ResolvedRoute:
    """Pick the best execution target for a model.

    Prefers the first target whose host is available. If none is available and
    include_unavailable is False, returns the first target marked unavailable so
    the caller can show it as "global best, not runnable here".
    """
    statuses = [target_status(t) for t in model.execution_targets]
    for t, s in zip(model.execution_targets, statuses, strict=True):
        if s.availability == AVAILABLE:
            return ResolvedRoute(t, s, statuses)
    if model.execution_targets:
        first = model.execution_targets[0]
        return ResolvedRoute(
            first if include_unavailable else None, statuses[0] if statuses else None, statuses
        )
    return ResolvedRoute(None, None, statuses)


def command_preview(target: ExecutionTarget, redact: bool = True) -> str:
    """Human-readable command preview; the prompt is redacted by default."""
    if not target.command_template:
        return f"(no command - {target.execution_mode.value} host '{target.host}')"
    argv = [
        ("<prompt redacted>" if redact and a == "{prompt}" else a) for a in target.command_template
    ]
    return " ".join(argv)


def known_hosts() -> list[str]:
    return [*_CLI_HOSTS, *_API_HOSTS, "manual"]
