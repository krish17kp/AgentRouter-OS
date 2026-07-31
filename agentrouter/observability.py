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
