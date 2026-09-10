"""TASK-002 — in-memory rate limiting + idempotency (backlog L6)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")  # optional [server] extra

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.server import limits as limits_mod  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402
from agentrouter.server.limits import (  # noqa: E402
    CachedResponse,
    IdempotencyCache,
    RateLimiter,
    client_key,
)

runner = CliRunner()


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def time(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture()
def client(home, monkeypatch):
    monkeypatch.delenv("AGENTROUTER_RATE_LIMIT", raising=False)
    return TestClient(create_app())


# ---- RateLimiter unit ----


def test_rate_limiter_disabled_by_default():
    rl = RateLimiter()  # reads env; unset -> 0 -> disabled
    assert all(rl.check("k") == (True, 0) for _ in range(100))


def test_rate_limiter_fixed_window():
    clock = FakeClock()
    rl = RateLimiter(limit=2, window=10, clock=clock.time)
    assert rl.check("k") == (True, 0)
    assert rl.check("k") == (True, 0)
    allowed, retry = rl.check("k")
    assert allowed is False and retry >= 1
    clock.advance(10)  # window rolls over
    assert rl.check("k") == (True, 0)


def test_rate_limiter_keys_are_independent():
    rl = RateLimiter(limit=1, window=10, clock=FakeClock().time)
    assert rl.check("a")[0] is True
    assert rl.check("b")[0] is True
    assert rl.check("a")[0] is False


def test_client_key_prefers_api_key():
    assert client_key("secret", "1.2.3.4") == "key:secret"
    assert client_key(None, "1.2.3.4") == "ip:1.2.3.4"
    assert client_key(None, None) == "ip:unknown"


# ---- IdempotencyCache unit ----


def test_idempotency_cache_ttl_expiry():
    clock = FakeClock()
    c = IdempotencyCache(ttl=5, clock=clock.time)
    c.put("k", CachedResponse(200, b"body", "application/json"))
    assert c.get("k").body == b"body"
    clock.advance(6)
    assert c.get("k") is None


def test_idempotency_cache_bounded(monkeypatch):
    monkeypatch.setattr(limits_mod, "MAX_ENTRIES", 3)
    c = IdempotencyCache(ttl=10_000, clock=FakeClock().time)  # nothing expires by TTL
    for i in range(10):
        c.put(f"k{i}", CachedResponse(200, str(i).encode(), None))
    assert len(c._store) <= 3  # oldest-first eviction keeps it bounded


def test_rate_limiter_bounded(monkeypatch):
    monkeypatch.setattr(limits_mod, "MAX_ENTRIES", 3)
    rl = RateLimiter(limit=100, window=10_000, clock=FakeClock().time)
    for i in range(10):
        rl.check(f"client{i}")  # distinct keys, none expired
    assert len(rl._buckets) <= 3


# ---- server integration ----


def test_rate_limit_disabled_lets_requests_through(client):
    for _ in range(10):
        assert client.get("/v1/models").status_code == 200


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_RATE_LIMIT", "3")
    monkeypatch.setenv("AGENTROUTER_RATE_WINDOW", "60")
    codes = [client.get("/v1/models").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]
    r = client.get("/v1/models")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) >= 1


def test_health_exempt_from_rate_limit(client, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_RATE_LIMIT", "1")
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_idempotent_post_replays_same_decision(client):
    headers = {"Idempotency-Key": "k-abc"}
    body = {"task": "summarize a PR"}
    r1 = client.post("/v1/route", json=body, headers=headers)
    r2 = client.post("/v1/route", json=body, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers.get("Idempotency-Replay") == "false"
    assert r2.headers.get("Idempotency-Replay") == "true"
    # Same decision id -> the second call did NOT create a new decision.
    assert r1.json()["decision_id"] == r2.json()["decision_id"]


def test_different_idempotency_key_not_replayed(client):
    body = {"task": "summarize a PR"}
    r1 = client.post("/v1/route", json=body, headers={"Idempotency-Key": "k1"})
    r2 = client.post("/v1/route", json=body, headers={"Idempotency-Key": "k2"})
    assert r1.json()["decision_id"] != r2.json()["decision_id"]


def test_post_without_key_not_cached(client):
    body = {"task": "summarize a PR"}
    r1 = client.post("/v1/route", json=body)
    r2 = client.post("/v1/route", json=body)
    # No idempotency header -> distinct decisions, no replay marker as "true".
    assert r1.json()["decision_id"] != r2.json()["decision_id"]
    assert r2.headers.get("Idempotency-Replay") != "true"


# ---- security regressions (from independent audit) ----


def test_idempotency_not_served_without_auth(tmp_path, monkeypatch):
    # HIGH fix: a cached POST response must not be replayed to an unauthenticated caller.
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTROUTER_API_KEY", "secret")
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    c = TestClient(create_app())
    body = {"task": "summarize a PR"}
    r1 = c.post("/v1/route", json=body, headers={"X-API-Key": "secret", "Idempotency-Key": "k"})
    assert r1.status_code == 200
    # same idempotency key, but no API key -> 401, never the cached 200.
    r2 = c.post("/v1/route", json=body, headers={"Idempotency-Key": "k"})
    assert r2.status_code == 401
    assert r2.headers.get("Idempotency-Replay") != "true"


def test_idempotency_body_change_not_replayed(client):
    # MEDIUM fix: reusing a key with a different body must not replay the old decision.
    hdr = {"Idempotency-Key": "same-key"}
    r1 = client.post("/v1/route", json={"task": "summarize a PR"}, headers=hdr)
    r2 = client.post("/v1/route", json={"task": "write a haiku about cats"}, headers=hdr)
    assert r2.headers.get("Idempotency-Replay") == "false"
    assert r1.json()["decision_id"] != r2.json()["decision_id"]


def test_non_2xx_not_cached(client):
    # MEDIUM fix: a 4xx must not be pinned under the key for the TTL.
    hdr = {"Idempotency-Key": "err-key"}
    bad = {"context_tokens": 5}  # missing required 'task' -> 422
    r1 = client.post("/v1/route", json=bad, headers=hdr)
    r2 = client.post("/v1/route", json=bad, headers=hdr)
    assert r1.status_code == 422 and r2.status_code == 422
    assert r2.headers.get("Idempotency-Replay") != "true"  # recomputed, not served from cache


def test_replay_preserves_content_type(client):
    # Bug A fix: replayed response must keep Content-Type (media_type is None in middleware).
    hdr = {"Idempotency-Key": "ct"}
    body = {"task": "summarize a PR"}
    client.post("/v1/route", json=body, headers=hdr)
    r2 = client.post("/v1/route", json=body, headers=hdr)
    assert r2.headers.get("Idempotency-Replay") == "true"
    assert r2.headers.get("content-type", "").startswith("application/json")


def test_request_id_present_on_replay(client):
    # Bug B fix: replay (a limits short-circuit) still carries X-Request-ID.
    hdr = {"Idempotency-Key": "rid"}
    body = {"task": "summarize a PR"}
    client.post("/v1/route", json=body, headers=hdr)
    r2 = client.post("/v1/route", json=body, headers=hdr)
    assert r2.headers.get("Idempotency-Replay") == "true"
    assert r2.headers.get("X-Request-ID")


def test_request_id_present_on_429(client, monkeypatch):
    # Bug B fix: a rate-limited 429 still carries X-Request-ID.
    monkeypatch.setenv("AGENTROUTER_RATE_LIMIT", "1")
    client.get("/v1/models")
    r = client.get("/v1/models")
    assert r.status_code == 429
    assert r.headers.get("X-Request-ID")


# --- single-flight locking (TASK-018B) ----------------------------------------
#
# `get` and `put` were each atomic but the window between them was not, so
# concurrent retries of one idempotency key all missed the cache and all ran the
# work — 12 replays produced 6 decisions. These pin the lock's exact semantics,
# because "returns a lock" is not the property that matters: returning the SAME
# lock for the same key is.


def test_flight_returns_the_same_lock_for_the_same_key():
    """A fresh lock per call would serialise nothing at all."""
    cache = limits_mod.IdempotencyCache()
    first = cache.flight("key-a")
    second = cache.flight("key-a")
    assert first is second


def test_flight_returns_different_locks_for_different_keys():
    """Otherwise one slow key would block every other caller."""
    cache = limits_mod.IdempotencyCache()
    assert cache.flight("key-a") is not cache.flight("key-b")


def test_release_flight_drops_an_idle_lock():
    """The map must not grow without bound across many distinct keys."""
    cache = limits_mod.IdempotencyCache()
    cache.flight("done")
    assert "done" in cache._flights
    cache.release_flight("done")
    assert "done" not in cache._flights


def test_release_flight_keeps_a_held_lock():
    """Dropping a held lock would let a waiter create a second one and proceed
    concurrently — reintroducing exactly the bug this fixes."""
    import asyncio

    cache = limits_mod.IdempotencyCache()

    async def hold_and_release():
        lock = cache.flight("busy")
        async with lock:
            cache.release_flight("busy")
            assert "busy" in cache._flights, "a held flight lock was dropped"
        # once released it can be reclaimed
        cache.release_flight("busy")
        assert "busy" not in cache._flights

    asyncio.run(hold_and_release())


def test_release_flight_on_an_unknown_key_is_a_no_op():
    cache = limits_mod.IdempotencyCache()
    cache.release_flight("never-seen")  # must not raise
    assert cache._flights == {}


def test_flight_locks_actually_serialise_the_same_key():
    """The behavioural property, not just the bookkeeping."""
    import asyncio

    cache = limits_mod.IdempotencyCache()
    order: list[str] = []

    async def worker(name: str):
        async with cache.flight("shared"):
            order.append(f"enter-{name}")
            await asyncio.sleep(0.01)
            order.append(f"exit-{name}")

    async def run():
        await asyncio.gather(worker("a"), worker("b"))

    asyncio.run(run())
    # No interleaving: each enter is immediately followed by its own exit.
    assert order[0].startswith("enter-") and order[1] == order[0].replace("enter", "exit")
    assert order[2].startswith("enter-") and order[3] == order[2].replace("enter", "exit")
