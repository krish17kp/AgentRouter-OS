"""Execution-host discovery + two-stage host resolution (program Phase 4/5).

Stage 1 (engine) picks a MODEL. Stage 2 (here) picks HOW to run it: the best
available execution host among the model's execution_targets. Detection is
read-only, offline-safe, and never reads or prints a credential value:

- CLI hosts (claude-code, codex-cli): `shutil.which(required_command)`, plus
  existence-only checks of the host's config dir / credential file.
- API hosts (anthropic-api, openai-api, gemini-api, openrouter): the required
  env var is present and non-blank (the value is only tested for emptiness).
- manual: always available; you run the command yourself.

Two levels of result (TASK-016):

* ``availability`` — the coarse routing signal, unchanged:
  available | unavailable | unknown. `unknown` is never promoted to
  `available`; default routing prefers models with an available host, and
  `execute` refuses anything that is not `available`.
* ``state`` — *why*, using the command.md PHASE C vocabulary:
  missing | installed | configured | authenticated | authorized | degraded |
  unknown, each paired with an actionable ``remedy``.

``authorized`` means a real authorization check succeeded. That needs the
opt-in live call PHASE C lists separately, so offline detection never returns
it — claiming it from local evidence alone would be a lie about the system.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .schema import ExecutionTarget, ModelEntry

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"

# Finer readiness states (command.md PHASE C line 526).
MISSING = "missing"  # prerequisite absent (no binary / no key)
INSTALLED = "installed"  # binary present, no local config yet
CONFIGURED = "configured"  # host config exists, no credential evidence
AUTHENTICATED = "authenticated"  # a credential is present (not proven valid)
AUTHORIZED = "authorized"  # verified by a live check — never inferred offline
DEGRADED = "degraded"  # present but unusable (blank key, not executable)
STATE_UNKNOWN = UNKNOWN

# state -> coarse availability. Keeps `availability` semantics identical to the
# pre-TASK-016 behavior for every case that existed before.
_AVAILABLE_STATES = frozenset({INSTALLED, CONFIGURED, AUTHENTICATED, AUTHORIZED})
_UNAVAILABLE_STATES = frozenset({MISSING, DEGRADED})


@dataclass(frozen=True)
class CliHost:
    """Offline evidence that a CLI host is installed / configured / authenticated."""

    command: str
    config_dir: str  # relative to the user's home
    credential_files: tuple[str, ...] = ()  # existence only; contents never read
    env_fallback: tuple[str, ...] = ()  # a key that also lets the CLI run


_CLI_HOSTS: dict[str, CliHost] = {
    "claude-code": CliHost(
        command="claude",
        config_dir=".claude",
        credential_files=(".credentials.json",),
        env_fallback=("ANTHROPIC_API_KEY",),
    ),
    "codex-cli": CliHost(
        command="codex",
        config_dir=".codex",
        credential_files=("auth.json",),
        env_fallback=("OPENAI_API_KEY",),
    ),
}
_API_HOSTS = {
    "anthropic-api": "ANTHROPIC_API_KEY",
    "openai-api": "OPENAI_API_KEY",
    "gemini-api": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# What to tell the user when the binary is absent vs. present-but-unauthenticated.
_INSTALL_HINT = {
    "claude-code": "install Claude Code, then run: claude login",
    "codex-cli": "install the Codex CLI, then authenticate it",
}
_AUTH_HINT = {
    "claude-code": "run: claude login",
    "codex-cli": "authenticate the Codex CLI",
}

# Rough remediation cost, used only to order `hosts doctor`'s suggested fix so it
# recommends the cheapest real fix rather than whichever host is listed first.
_FIX_COST_DEGRADED = 0  # a value is wrong — just correct it
_FIX_COST_MISSING_ENV = 1  # export one variable
_FIX_COST_MISSING_BINARY = 2  # install (and then authenticate) a tool
_FIX_COST_OTHER = 3


def _availability_for(state: str) -> str:
    if state in _AVAILABLE_STATES:
        return AVAILABLE
    if state in _UNAVAILABLE_STATES:
        return UNAVAILABLE
    return UNKNOWN


def _home_dir() -> Path:
    """The user's home directory. Indirection keeps host detection testable."""
    return Path.home()


def _safe_exists(path: Path) -> bool:
    """Existence check that never raises. Contents are never opened.

    `Path.exists()`/`is_dir()` still propagate EACCES and ENAMETOOLONG, which is
    reachable in ordinary setups (a container whose HOME points at a directory
    the user cannot traverse, NFS root_squash). Detection must degrade to "no
    evidence", never crash `hosts doctor`, `route`, `execute` or the REST API.
    """
    try:
        return path.exists()
    except OSError:
        return False


def _safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _sanitize(value: str) -> str:
    """Strip control/escape characters from text echoed to a terminal.

    `required_command` comes from the model registry, which a local user can
    edit; without this a crafted value could emit ANSI escapes and forge a
    readiness line (overwriting its own output to fake an 'authenticated' host).
    """
    return "".join(c if c.isprintable() else "?" for c in value)[:120]


def _env_is_set(name: str) -> bool:
    """True when the env var holds a non-blank value. The value is never read out."""
    return bool((os.environ.get(name) or "").strip())


def _env_is_blank(name: str) -> bool:
    """True when the var exists but is empty/whitespace — set, yet unusable."""
    return name in os.environ and not (os.environ.get(name) or "").strip()


@dataclass(frozen=True)
class HostStatus:
    host: str
    availability: str
    reason: str
    state: str = STATE_UNKNOWN
    remedy: str | None = None  # concrete next step when not ready


def _status(host: str, state: str, reason: str, remedy: str | None = None) -> HostStatus:
    return HostStatus(host, _availability_for(state), reason, state, remedy)


def fix_cost(status: HostStatus) -> int:
    """Cheapest-fix-first ordering for diagnostics. Not a security boundary."""
    if status.state == DEGRADED:
        return _FIX_COST_DEGRADED
    if status.state == MISSING:
        return _FIX_COST_MISSING_ENV if status.host in _API_HOSTS else _FIX_COST_MISSING_BINARY
    return _FIX_COST_OTHER


def _detect_cli_host(host: str, meta: CliHost | None, cmd: str) -> HostStatus:
    # `cmd` may come from a registry-declared required_command, so it is only
    # ever echoed sanitized — never allowed to emit terminal escapes.
    shown = _sanitize(cmd)
    # shutil.which already filters on os.X_OK, so a hit is a runnable binary.
    if not shutil.which(cmd):
        hint = _INSTALL_HINT.get(host, f"install '{shown}' and make sure it is on PATH")
        return _status(host, MISSING, f"'{shown}' not found on PATH", hint)
    if meta is None:  # target-declared command we have no metadata for
        return _status(host, INSTALLED, f"'{shown}' found on PATH")

    # Positive evidence first, so a working CLI login (keychain/profile auth, no
    # credential file) is never overridden by an unrelated blank env var.
    home = _home_dir()
    for cred in meta.credential_files:
        if _safe_exists(home / meta.config_dir / cred):
            return _status(
                host, AUTHENTICATED, f"'{shown}' on PATH; credentials found in ~/{meta.config_dir}"
            )
    for env in meta.env_fallback:
        if _env_is_set(env):
            return _status(host, AUTHENTICATED, f"'{shown}' on PATH; {env} is set")
    if _safe_is_dir(home / meta.config_dir):
        return _status(
            host,
            CONFIGURED,
            f"'{shown}' on PATH; ~/{meta.config_dir} exists but no credentials found",
            _AUTH_HINT.get(host, f"authenticate '{shown}'"),
        )
    # Only now, with no other evidence, does a blank fallback key matter.
    for env in meta.env_fallback:
        if _env_is_blank(env):
            return _status(
                host,
                DEGRADED,
                f"'{shown}' on PATH but {env} is set to an empty value",
                f"unset {env}, or set it to a real key",
            )
    return _status(
        host,
        INSTALLED,
        f"'{shown}' found on PATH; not configured yet",
        _AUTH_HINT.get(host, f"authenticate '{shown}'"),
    )


def _detect_api_host(host: str, env: str) -> HostStatus:
    if _env_is_blank(env):
        return _status(
            host,
            DEGRADED,
            f"{env} is set but empty",
            f"set {env} to a real key, or unset it to use another host",
        )
    if _env_is_set(env):
        return _status(host, AUTHENTICATED, f"{env} is set")
    return _status(host, MISSING, f"{env} is not set", f"export {env}=<your key>")


def detect_host(host: str, required_command: str | None = None) -> HostStatus:
    """Read-only readiness check for one host. Never runs the tool or reads secrets."""
    if host == "manual":
        return _status(host, CONFIGURED, "manual execution is always available")
    meta = _CLI_HOSTS.get(host)
    cmd = required_command or (meta.command if meta else None)
    if meta is not None or (required_command and host not in _API_HOSTS):
        if not cmd:
            return _status(host, STATE_UNKNOWN, "no command declared; cannot verify")
        return _detect_cli_host(host, meta, cmd)
    if host in _API_HOSTS:
        return _detect_api_host(host, _API_HOSTS[host])
    return _status(
        host,
        STATE_UNKNOWN,
        "unrecognized host; cannot verify availability",
        "check the host id in your registry, or run: agentrouter hosts list",
    )


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


def execution_route_block(row: dict | None, models_by_key: dict[str, ModelEntry]) -> dict | None:
    """Stage-2 route block: resolve HOW to run the selected model (program Phase 5/6).

    JSON-serializable; None if the model has no execution targets. Shared by the
    CLI, REST, and MCP surfaces so their payloads never drift. No process is run.
    """
    if row is None:
        return None
    model = models_by_key.get(row["model"])
    if model is None or not model.execution_targets:
        return None
    resolved = resolve_execution_route(model, include_unavailable=True)
    tgt, status = resolved.target, resolved.status
    return {
        "vendor": model.vendor,
        "model_id": model.model_id,
        "display_name": model.name,
        "release_channel": model.release_channel.value,
        "host": tgt.host if tgt else None,
        "host_model_id": tgt.host_model_id if tgt else None,
        "execution_mode": tgt.execution_mode.value if tgt else None,
        "availability": status.availability if status else "unknown",
        "availability_reason": status.reason if status else "no execution target",
        # additive (TASK-016): finer readiness detail; `availability` is unchanged
        "host_state": status.state if status else STATE_UNKNOWN,
        "host_remedy": status.remedy if status else None,
        "command_preview": command_preview(tgt) if tgt else None,
        "required_env": tgt.required_env if tgt else [],
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "all_hosts": [
            {"host": s.host, "availability": s.availability, "state": s.state}
            for s in resolved.all_statuses
        ],
    }
