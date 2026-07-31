"""In-memory rate limiting + idempotency for the local server (TASK-002 / backlog L6).

Both are process-local and safe-by-default:
- **Rate limiting** is DISABLED unless ``AGENTROUTER_RATE_LIMIT`` > 0. When enabled,
  a fixed-window counter keyed by API key (else client host) rejects excess requests
  with 429 + ``Retry-After``.
- **Idempotency** activates only when a request carries an ``Idempotency-Key`` header;
  the first response (status + body) is cached for a TTL and replayed on repeats,
  so a client's retry never produces a second decision.

ponytail: fixed-window (not sliding) counters + dict stores under a lock. Single
process only — not a distributed limiter; run one worker or add shared state if you
scale out. Env is read lazily per call so it can be tuned per test/deployment.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

RATE_LIMIT_ENV = "AGENTROUTER_RATE_LIMIT"  # max requests per window; 0/unset = disabled
RATE_WINDOW_ENV = "AGENTROUTER_RATE_WINDOW"  # window length in seconds
IDEMPOTENCY_TTL_ENV = "AGENTROUTER_IDEMPOTENCY_TTL"  # cached-response lifetime in seconds
DEFAULT_WINDOW = 60
DEFAULT_IDEMPOTENCY_TTL = 300
# ponytail: bound both stores so a client spraying unique keys can't exhaust memory.
# Flat cap + oldest-first eviction; swap for an LRU only if a real workload needs it.
MAX_ENTRIES = 10_000

# Liveness/readiness probes must never be throttled.
RATE_EXEMPT_PATHS = frozenset({"/health", "/ready"})


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def client_key(api_key: str | None, host: str | None) -> str:
    """Rate-limit bucket key: prefer the API key, else the client host."""
    if api_key:
        return f"key:{api_key}"
    return f"ip:{host or 'unknown'}"


class RateLimiter:
    """Fixed-window per-key counter. A no-op while the configured limit is <= 0."""

    def __init__(self, limit: int | None = None, window: int | None = None, clock=time.monotonic):
        self._limit = limit
        self._window = window
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, int]] = {}  # key -> (window_start, count)

    @property
    def limit(self) -> int:
        return self._limit if self._limit is not None else _int_env(RATE_LIMIT_ENV, 0)

    @property
    def window(self) -> int:
        if self._window is not None:
            return self._window
        return _int_env(RATE_WINDOW_ENV, DEFAULT_WINDOW)

    def check(self, key: str) -> tuple[bool, int]:
        """Count one hit for ``key``. Returns (allowed, retry_after_seconds)."""
        limit = self.limit
        if limit <= 0:
            return True, 0
        window = max(1, self.window)
        now = self._clock()
        with self._lock:
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= window:
                start, count = now, 0
            count += 1
            self._buckets[key] = (start, count)
            if len(self._buckets) > MAX_ENTRIES:
                self._evict_locked(now, window)
        if count > limit:
            return False, max(1, int(window - (now - start)))
        return True, 0

    def _evict_locked(self, now: float, window: int) -> None:
        """Drop expired windows; if still over cap, drop oldest-inserted keys."""
        for k in [k for k, (s, _) in self._buckets.items() if now - s >= window]:
            del self._buckets[k]
        while len(self._buckets) > MAX_ENTRIES:
            self._buckets.pop(next(iter(self._buckets)))


@dataclass(frozen=True)
class CachedResponse:
    status: int
    body: bytes
    media_type: str | None


class IdempotencyCache:
    """TTL cache of prior responses keyed by the client's idempotency key."""

    def __init__(self, ttl: int | None = None, clock=time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, CachedResponse]] = {}

    @property
    def ttl(self) -> int:
        if self._ttl is not None:
            return self._ttl
        return _int_env(IDEMPOTENCY_TTL_ENV, DEFAULT_IDEMPOTENCY_TTL)

    def get(self, key: str) -> CachedResponse | None:
        now = self._clock()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            ts, resp = item
            if now - ts > self.ttl:
                del self._store[key]
                return None
            return resp

    def put(self, key: str, resp: CachedResponse) -> None:
        with self._lock:
            if key not in self._store and len(self._store) >= MAX_ENTRIES:
                self._evict_locked()
            self._store[key] = (self._clock(), resp)

    def _evict_locked(self) -> None:
        """Drop expired entries; if still at cap, drop oldest-inserted."""
        now, ttl = self._clock(), self.ttl
        for k in [k for k, (ts, _) in self._store.items() if now - ts > ttl]:
            del self._store[k]
        while len(self._store) >= MAX_ENTRIES:
            self._store.pop(next(iter(self._store)))
