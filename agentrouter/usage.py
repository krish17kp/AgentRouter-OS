"""Usage/quota intelligence (Production Milestone 1).

`hosts.py` answers "can we reach this provider" (installed / configured /
authenticated / authorized). This module answers a different question: "does
this provider still have budget left" — something most providers don't
expose at all without a live, credentialed, provider-specific call.

PROVIDER_ADAPTER_SPEC.md stages authenticated calls deliberately: catalog-only
in v1, a read-only key for `refresh_models` at Capstone, `execute` at
Production-future. A live quota/usage check is a third kind of authenticated
call the spec does not cover yet, and BACKLOG.yaml tracks it separately as P2
("live host access verification, needs: opt-in network + credentials") —
blocked on owner-provided credentials, not on missing code. So no adapter is
registered in `_LIVE_CHECKS` today: every real provider honestly reports
UNSUPPORTED when a live check is requested. `register_live_check` is the
extension point a future credentialed adapter uses; tests register a fake one
to prove the mechanism end-to-end without a network call.

Never fabricates a number: a remaining/reset_at value is populated only when
a live check actually returned one.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

UNKNOWN = "unknown"  # provider might expose quota; no live check was requested
UNSUPPORTED = "unsupported"  # no adapter can answer this for this provider
AVAILABLE = "available"  # live check: budget remains
EXHAUSTED = "exhausted"  # live check: no budget left
ERROR = "error"  # live check attempted and failed (timeout, HTTP, parse)

_STATES = frozenset({UNKNOWN, UNSUPPORTED, AVAILABLE, EXHAUSTED, ERROR})

_DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class UsageStatus:
    provider: str
    state: str
    detail: str
    remaining: float | None = None  # provider-native unit; None when not reported
    reset_at: str | None = None  # ISO-8601 UTC; None when not reported
    checked_at: float | None = None  # epoch seconds; None when never checked live
    source: str = "none"  # "none" | "live"

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state,
            "detail": self.detail,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "checked_at": self.checked_at,
            "source": self.source,
        }


def _sanitize(value: str) -> str:
    """Strip control/escape characters from adapter-supplied text before it reaches a
    terminal, JSON payload, or the decision log (same risk `hosts._sanitize` guards:
    a crafted value could emit ANSI escapes and forge output, or leak into a log
    verbatim). A live check is untrusted provider output, not our own code.
    """
    return "".join(c if c.isprintable() else "?" for c in value)[:200]


# provider id -> live-check function. Empty in production; tests populate a
# fake entry. A future credentialed adapter registers a real one here.
_LIVE_CHECKS: dict[str, Callable[[float], UsageStatus]] = {}


def register_live_check(provider: str, fn: Callable[[float], UsageStatus]) -> None:
    """Extension hook for a future adapter (or a test double). Not called in production."""
    _LIVE_CHECKS[provider] = fn


def unregister_live_check(provider: str) -> None:
    """Test-only teardown counterpart to `register_live_check`."""
    _LIVE_CHECKS.pop(provider, None)


def check_usage(
    provider: str, *, live: bool = False, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> UsageStatus:
    """Quota state for one provider. Never raises; never invents a number."""
    if not live:
        return UsageStatus(provider, UNKNOWN, "live verification not requested", source="none")
    fn = _LIVE_CHECKS.get(provider)
    if fn is None:
        return UsageStatus(
            provider, UNSUPPORTED, f"no live usage check registered for '{provider}'", source="none"
        )
    # A registered adapter's own `timeout` argument is a courtesy, not a
    # guarantee (a blocking C extension, a stuck DNS lookup); enforce a real
    # wall-clock bound here so one slow provider can never hang `doctor`/
    # `route` past what the CLI help promises. `shutdown(wait=False)` on
    # timeout deliberately abandons the still-running thread rather than
    # blocking on it — this function must return within `timeout`, not
    # within however long the misbehaving adapter actually takes.
    #
    # `future.result(timeout=...)` is deliberately NOT used to detect a
    # timeout: as of Python 3.11, `concurrent.futures.TimeoutError` is the
    # same class as the builtin `TimeoutError`, so an adapter that itself
    # raises `TimeoutError` (a perfectly reasonable thing for a network
    # adapter to do) would be misreported as *our* timeout. `wait()` first
    # keeps "the call never finished" and "the call finished and raised"
    # unambiguous regardless of Python version.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, timeout)
    done, not_done = wait([future], timeout=timeout)
    if not_done:
        pool.shutdown(wait=False)
        return UsageStatus(
            provider,
            ERROR,
            f"live check exceeded the {timeout}s timeout",
            checked_at=time.time(),
            source="live",
        )
    try:
        status = future.result()  # already finished; this only re-raises, never blocks
    except Exception as exc:  # noqa: BLE001 - isolate one provider's failure from the caller
        pool.shutdown(wait=False)
        return UsageStatus(
            provider,
            ERROR,
            f"live check failed ({type(exc).__name__})",
            checked_at=time.time(),
            source="live",
        )
    pool.shutdown(wait=False)
    if not isinstance(status, UsageStatus) or status.state not in _STATES:
        return UsageStatus(
            provider,
            ERROR,
            "live check returned an unrecognized result",
            checked_at=time.time(),
            source="live",
        )
    return UsageStatus(
        status.provider,
        status.state,
        _sanitize(status.detail),
        remaining=status.remaining,
        reset_at=status.reset_at,
        checked_at=status.checked_at,
        source=status.source,
    )


def apply_live_verification(
    result: dict[str, Any],
    models: list,
    models_by_key: dict[str, Any],
    cls,
    weights: dict[str, float],
    prefer: str | None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """If the top pick's provider is live-verified EXHAUSTED, re-rank without it.

    Returns a new result dict annotated with `usage_check`; the input `result`
    (from `engine.route`) is never mutated. Imports `engine.route` locally so
    this impure, network-adjacent module stays a one-way dependency: engine.py
    (pure scoring) never imports usage.py.

    # ponytail: checks the new top pick's quota once, not recursively — a
    # second live-EXHAUSTED pick in a row still gets recommended. Escalate to
    # a loop (with a max-attempts bound) once a real adapter makes that a
    # reachable case; today `_LIVE_CHECKS` is empty in production, so it
    # isn't.
    """
    rec = result.get("recommendation")
    if rec is None:
        return result

    top_model = models_by_key[rec["model"]]
    status = check_usage(top_model.provider, live=True, timeout=timeout)
    annotated = {**result, "usage_check": status.as_dict()}
    if status.state != EXHAUSTED:
        return annotated

    from .engine import route as engine_route

    remaining_models = [m for m in models if m.key != top_model.key]
    retry = engine_route(remaining_models, cls, weights, prefer=prefer)
    # `retry`'s own `excluded` is eligibility() re-run over `remaining_models`;
    # since eligibility is a pure per-model filter, it reproduces exactly the
    # same entries `result["excluded"]` already has (eligibility never depends
    # on which other models are present) — concatenating both would duplicate
    # every one of them, so only the new quota-exclusion entry is added here.
    retry["excluded"] = [
        {"model": top_model.key, "reason": f"quota exhausted (live-verified): {status.detail}"},
        *result["excluded"],
    ]
    retry["weight_shifts"] = [
        *result["weight_shifts"],
        f"quota exhausted for {top_model.provider}; re-ranked excluding {top_model.key}",
    ]
    retry["usage_check"] = status.as_dict()
    return retry
