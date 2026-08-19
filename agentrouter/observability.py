"""Opt-in structured logging + OpenTelemetry for route decisions (TASK-001 / backlog L1).

Design goals:
- **Structured:** one JSON record per route decision on the ``agentrouter.route``
  logger, correlatable by request id.
- **Private by default:** never logs raw task text or generated prompts — only
  metadata (task length, task type, risk, chosen model).
- **Zero hard dependency:** OpenTelemetry is optional. Spans are a no-op unless
  ``AGENTROUTER_OTEL`` is truthy *and* ``opentelemetry`` is importable.
- **Silent by default:** the library never configures handlers; INFO records go
  nowhere until ``configure_logging()`` is called (opt-in via ``AGENTROUTER_LOG``)
  or the host app installs its own handler. Existing CLI output is unchanged.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import re
import traceback
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger("agentrouter.route")

_LOG_ENV = "AGENTROUTER_LOG"
_OTEL_ENV = "AGENTROUTER_OTEL"

# Propagates a request id (e.g. the server's X-Request-ID) into deeper layers
# without threading it through every function signature.
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentrouter_request_id", default=None
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def otel_enabled() -> bool:
    """True only when explicitly opted in via env AND opentelemetry is importable."""
    if not _truthy(os.environ.get(_OTEL_ENV)):
        return False
    try:
        import opentelemetry.trace  # noqa: F401
    except ImportError:
        return False
    return True


def configure_logging(*, force: bool = False) -> bool:
    """Attach a stderr handler that prints the raw JSON record, if opted in.

    No-op unless ``AGENTROUTER_LOG`` is truthy (or ``force``). Idempotent. Returns
    True if logging is now active. Kept out of import side effects on purpose.
    """
    if not force and not _truthy(os.environ.get(_LOG_ENV)):
        return False
    if not any(getattr(h, "_agentrouter", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._agentrouter = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return True


def route_decision_record(
    *,
    task: str,
    payload: dict[str, Any],
    decision_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the JSON-safe decision record. Never includes raw task text/prompt."""
    cls = payload.get("classification") or {}
    rec = payload.get("recommendation") or {}
    gates = payload.get("gates") or {}
    record: dict[str, Any] = {
        "event": "route_decision",
        "request_id": request_id if request_id is not None else get_request_id(),
        "decision_id": decision_id,
        "task_type": cls.get("task_type"),
        "risk": cls.get("risk"),
        "confidence": cls.get("confidence"),
        "recommended_model": rec.get("model"),
        "provider": rec.get("provider"),
        "pricing_tier": rec.get("pricing_tier"),
        "score": rec.get("score"),
        "auto_execute_allowed": gates.get("auto_execute_allowed"),
        "excluded_count": len(payload.get("excluded") or []),
        "task_len": len(task or ""),
    }
    # Drop unset keys so records stay compact and stable.
    return {k: v for k, v in record.items() if v is not None}


def log_route_decision(
    *,
    task: str,
    payload: dict[str, Any],
    decision_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Emit one structured route-decision record. Returns the record for testing."""
    record = route_decision_record(
        task=task, payload=payload, decision_id=decision_id, request_id=request_id
    )
    logger.info(json.dumps(record, sort_keys=True))
    return record


# Credential shapes. A vendor-prefix list alone is a losing game — it missed
# Google, GitLab, Slack, HuggingFace, fine-grained GitHub PATs, AWS *temporary*
# keys and every `password=` pair — so the last two alternatives are generic:
# a keyword adjacent to a value, and any long high-entropy run. Over-redaction
# is the correct failure direction here; a log is not worth a leaked key.
_SECRET_RE = re.compile(
    r"""(
      -----BEGIN[ A-Z]*PRIVATE\ KEY-----.*?-----END[ A-Z]*PRIVATE\ KEY-----
    | sk-[A-Za-z0-9_\-]{8,}
    | sk_(?:live|test)_[A-Za-z0-9]{8,}
    | github_pat_[A-Za-z0-9_]{20,}
    | gh[pousr]_[A-Za-z0-9]{16,}
    | glpat-[A-Za-z0-9_\-]{16,}
    | xox[baprs]-[A-Za-z0-9\-]{10,}
    | hf_[A-Za-z0-9]{16,}
    | AIza[A-Za-z0-9_\-]{20,}
    | A(?:KIA|SIA|ROA|IDA|NPA|NVA)[0-9A-Z]{12,}
    | (?:Bearer|Basic)\s+[A-Za-z0-9+/=._\-]{8,}
    | ey[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]+
    | [a-z][a-z0-9+.\-]*://[^\s/@]+:[^\s/@]+@
    | (?i:api[_\-]?key|secret|passwd|password|token|credential)
      (?-i:)["'\s]*[:=]["'\s]*[^\s"',}\]]{6,}
    | [A-Za-z0-9+/]{40,}={0,2}
    )""",
    re.VERBOSE | re.DOTALL,
)

_MAX_REDACT_DEPTH = 6


def _is_probably_a_path(run: str) -> bool:
    """True for a filesystem path that the catch-all pattern would otherwise mask.

    The last alternative in `_SECRET_RE` is a deliberate catch-all for long
    opaque runs, and it did its job too well: `.../Projects/Agentrouteros/
    agentrouter/server/app` is 44 characters of `[A-Za-z0-9+/]` and was redacted
    out of every traceback, exactly where a path is the most useful thing on the
    line.

    The discriminator is a digit. Path segments are words; opaque tokens are
    not, and every realistic long secret that contains a slash (an AWS secret
    access key, a base64 blob) also contains at least one digit. This narrows
    only the catch-all — the vendor prefixes, keyword adjacency, JWT, PEM and
    connection-string rules are untouched, so nothing that was named before is
    unmasked now.
    """
    return "/" in run and not any(character.isdigit() for character in run)


def redact(text: str) -> str:
    """Mask credential-shaped substrings before anything is written to a log."""

    def mask(match: re.Match[str]) -> str:
        run = match.group(0)
        return run if _is_probably_a_path(run) else "[redacted]"

    return _SECRET_RE.sub(mask, text)


def redact_value(value: Any, _depth: int = 0) -> Any:
    """Redact recursively, so a credential inside a dict or list cannot slip past.

    ``log_event`` used to redact only values that were already strings, so
    ``detail={"authorization": "Bearer secret"}`` was serialised untouched.
    """
    if isinstance(value, str):
        return redact(value)
    if _depth >= _MAX_REDACT_DEPTH:
        return redact(str(value))
    if isinstance(value, dict):
        return {k: redact_value(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact_value(v, _depth + 1) for v in value]
    return value


def log_event(event: str, **fields: Any) -> dict[str, Any]:
    """Emit one structured event record. Returns the record for testing.

    Pass metadata only — never raw task text, prompts or credential values. The
    current request id is attached automatically so an operator can correlate an
    event with the API response the client saw. String values are passed through
    ``redact`` as a backstop, because the most valuable events (unexpected
    failures) carry text nobody enumerated in advance.
    """
    record: dict[str, Any] = {"event": event, "request_id": get_request_id(), **fields}
    record = {k: redact_value(v) for k, v in record.items() if v is not None}
    logger.info(json.dumps(record, sort_keys=True, default=str))
    return record


def log_api_error(
    event: str, exc: BaseException, *, detail: bool = True, remedy: str | None = None
) -> dict[str, Any]:
    """Record a server-side failure so it is diagnosable even though the client is told nothing.

    Emitted at ERROR. The module is silent by design at INFO, which is right for
    routine records but wrong here: catching an unhandled API error to return a
    typed 500 also stops the ASGI server from logging it, so without an
    ERROR-level record the fault would be invisible to the operator. Note that
    ERROR records are *not* silent even with no handler installed — Python's
    ``lastResort`` handler writes them to stderr. That is deliberate for a fault,
    and it is why ``detail`` exists.

    ``detail=False`` logs the type and a remedy but neither the exception text
    nor a traceback. Use it when the exception is **the user's data being wrong
    rather than a bug**: such messages quote the offending file and its contents,
    so logging them turns any caller who can reach the failing endpoint into an
    unauthenticated amplifier that writes that content — credentials included —
    into the operator's log on every request. A malformed registry is exactly
    that case, and `/ready` is both unauthenticated and rate-limit exempt.

    When ``detail`` is on, the traceback is rendered and redacted here rather
    than passed as ``exc_info``: logging would otherwise render the raw exception
    message, and that message is precisely where a stray credential shows up.
    """
    record: dict[str, Any] = {
        "event": event,
        "request_id": get_request_id(),
        "error_type": type(exc).__name__,
    }
    if detail:
        record["message"] = redact(str(exc))[:500]
    if remedy:
        record["remedy"] = remedy
    record = {k: v for k, v in record.items() if v is not None}
    line = json.dumps(record, sort_keys=True, default=str)
    if not detail:
        logger.error("%s", line)
        return record
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("%s\n%s", line, redact(trace))
    return record


@contextlib.contextmanager
def route_span(name: str = "route", **attributes: Any) -> Iterator[Any]:
    """Start an OTel span if opted in; otherwise a zero-cost no-op yielding None.

    Pass metadata attributes only (task_type, risk, model key) — never raw task
    text or generated prompts, which would be exported to the tracing backend.
    """
    if not otel_enabled():
        yield None
        return
    from opentelemetry import trace  # import guarded by otel_enabled()

    tracer = trace.get_tracer("agentrouter")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span
