"""Drive the real app over loopback and reconcile what actually happened.

Why loopback and not ``TestClient``: the first concurrency defect this lab found
— ``sqlite3.OperationalError: database is locked`` surfacing as HTTP 500 — does
**not** reproduce through ``TestClient`` at 40 concurrent requests, but does
reproduce at 200 against a real uvicorn server. A harness built on TestClient
alone would have declared the API healthy. Real sockets, real event loop, real
threadpool.
"""

from __future__ import annotations

import contextlib
import statistics
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Requests that a well-behaved server may legitimately return under load. Any
# other 5xx is a defect, not a capacity signal.
_EXPECTED_STATUSES = frozenset({200, 201, 404, 409, 422, 429})


@dataclass(frozen=True)
class LoadSpec:
    """What to send. Deterministic by construction: no randomness, no sleeps."""

    total: int = 200
    workers: int = 32
    timeout_seconds: float = 30.0
    #: Builds (method, path, json_body) for request ``i``.
    request: Callable[[int], tuple[str, str, dict | None]] | None = None

    def build(self, index: int) -> tuple[str, str, dict | None]:
        if self.request is not None:
            return self.request(index)
        return "POST", "/v1/route", {"task": f"refactor module {index}"}


@dataclass
class LoadOutcome:
    """What happened. Correctness fields are gated; timing fields are reported."""

    statuses: Counter = field(default_factory=Counter)
    transport_errors: Counter = field(default_factory=Counter)
    latencies_ms: list[float] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    request_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> int:
        return self.statuses.get(200, 0)

    @property
    def unexpected(self) -> dict[int, int]:
        """Status codes a healthy server should never produce under load."""
        return {s: n for s, n in self.statuses.items() if s not in _EXPECTED_STATUSES}

    @property
    def server_errors(self) -> int:
        return sum(n for s, n in self.statuses.items() if 500 <= s < 600)

    @property
    def throughput(self) -> float:
        return len(self.latencies_ms) / self.elapsed_seconds if self.elapsed_seconds else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        index = min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1))))
        return ordered[index]

    def as_dict(self) -> dict[str, Any]:
        return {
            "requests": sum(self.statuses.values()) + sum(self.transport_errors.values()),
            "statuses": dict(sorted(self.statuses.items())),
            "transport_errors": dict(sorted(self.transport_errors.items())),
            "unexpected_statuses": self.unexpected,
            "server_errors": self.server_errors,
            "distinct_request_ids": len(set(self.request_ids)),
            # Timing is INDICATIVE ONLY. It is reported so a regression is
            # visible to a human, and deliberately never asserted in CI.
            "timing_indicative_only": {
                "elapsed_seconds": round(self.elapsed_seconds, 3),
                "throughput_per_second": round(self.throughput, 1),
                "p50_ms": round(self.percentile(50), 1),
                "p95_ms": round(self.percentile(95), 1),
                "p99_ms": round(self.percentile(99), 1),
                "mean_ms": round(statistics.fmean(self.latencies_ms), 1)
                if self.latencies_ms
                else 0.0,
            },
        }


@dataclass
class RunningApp:
    url: str
    home: Path
    _server: Any

    def stop(self) -> None:
        self._server.should_exit = True


@contextlib.contextmanager
def serve_app(home: Path, *, app: Any | None = None) -> Iterator[RunningApp]:
    """Serve the real app on an ephemeral loopback port for the duration."""
    import uvicorn

    from agentrouter.server.app import create_app

    config = uvicorn.Config(app or create_app(), host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 60
    while not server.started and time.time() < deadline:
        time.sleep(0.01)
    if not server.started:  # pragma: no cover - only on a wedged machine
        raise RuntimeError("the load-lab server did not start within 60s")
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield RunningApp(f"http://127.0.0.1:{port}", home, server)
    finally:
        server.should_exit = True
        thread.join(timeout=30)


def run_load(url: str, spec: LoadSpec) -> LoadOutcome:
    """Fire ``spec.total`` requests through ``spec.workers`` threads.

    Threads rather than asyncio on purpose: the endpoints are sync `def`, so
    they run on Starlette's threadpool, and driving them from threads exercises
    the same contention a real multi-client workload produces.
    """
    import httpx

    outcome = LoadOutcome()
    lock = threading.Lock()
    queue = list(range(spec.total))
    cursor = threading.Lock()
    position = [0]

    def take() -> int | None:
        with cursor:
            if position[0] >= len(queue):
                return None
            index = queue[position[0]]
            position[0] += 1
            return index

    def worker() -> None:
        with httpx.Client(timeout=spec.timeout_seconds) as client:
            while True:
                index = take()
                if index is None:
                    return
                method, path, body = spec.build(index)
                started = time.perf_counter()
                try:
                    response = client.request(method, f"{url}{path}", json=body)
                except Exception as exc:  # transport-level, not an HTTP status
                    with lock:
                        outcome.transport_errors[type(exc).__name__] += 1
                    continue
                elapsed_ms = (time.perf_counter() - started) * 1000
                with lock:
                    outcome.statuses[response.status_code] += 1
                    outcome.latencies_ms.append(elapsed_ms)
                    rid = response.headers.get("X-Request-ID")
                    if rid:
                        outcome.request_ids.append(rid)

    threads = [threading.Thread(target=worker) for _ in range(spec.workers)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    outcome.elapsed_seconds = time.perf_counter() - started
    return outcome
