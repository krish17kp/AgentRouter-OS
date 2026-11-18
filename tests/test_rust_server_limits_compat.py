"""Python/Rust contract checks for process-local server limits."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(request):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "limits_from_json",
            "-p",
            "agentrouter-cli",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def test_rust_client_key_matches_python():
    from agentrouter.server.limits import client_key

    for api_key, host in (("secret", "1.2.3.4"), ("", "1.2.3.4"), (None, ""), (None, None)):
        process = _rust({"operation": "client_key", "api_key": api_key, "host": host})
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout)["key"] == client_key(api_key, host)


def test_rust_rate_limiter_matches_python_fixed_window_and_retry():
    from agentrouter.server.limits import RateLimiter

    now = [100.0]
    python_limiter = RateLimiter(limit=2, window=10, clock=lambda: now[0])
    hits = [
        {"key": "a", "now": 100.0},
        {"key": "a", "now": 101.0},
        {"key": "a", "now": 102.0},
        {"key": "b", "now": 102.0},
        {"key": "a", "now": 110.0},
    ]
    expected = []
    for hit in hits:
        now[0] = hit["now"]
        allowed, retry_after = python_limiter.check(hit["key"])
        expected.append({"allowed": allowed, "retry_after": retry_after})

    process = _rust({"operation": "rate", "limit": 2, "window": 10, "hits": hits})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["results"] == expected


def test_rust_idempotency_cache_matches_python_ttl_and_response_fields():
    from agentrouter.server.limits import CachedResponse, IdempotencyCache

    now = [10.0]
    python_cache = IdempotencyCache(ttl=5, clock=lambda: now[0])
    response = CachedResponse(201, b'{"ok":true}', "application/json")
    python_cache.put("key", response)
    actions = [
        {
            "action": "put",
            "key": "key",
            "now": 10.0,
            "response": {
                "status": 201,
                "body": response.body.decode(),
                "media_type": response.media_type,
            },
        },
        {"action": "get", "key": "key", "now": 15.0},
        {"action": "get", "key": "key", "now": 15.01},
    ]
    expected = []
    for action in actions:
        now[0] = action["now"]
        if action["action"] == "put":
            python_cache.put(action["key"], response)
            expected.append({"cached": True})
        else:
            cached = python_cache.get(action["key"])
            expected.append(
                {
                    "response": None
                    if cached is None
                    else {
                        "status": cached.status,
                        "body": cached.body.decode(),
                        "media_type": cached.media_type,
                    }
                }
            )

    process = _rust({"operation": "cache", "ttl": 5, "actions": actions})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["results"] == expected


def test_rust_limits_read_environment_settings_like_python(monkeypatch):
    from agentrouter.server.limits import CachedResponse, IdempotencyCache, RateLimiter

    monkeypatch.setenv("AGENTROUTER_RATE_LIMIT", "2")
    monkeypatch.setenv("AGENTROUTER_RATE_WINDOW", "10")
    monkeypatch.setenv("AGENTROUTER_IDEMPOTENCY_TTL", "5")

    now = [100.0]
    python_limiter = RateLimiter(clock=lambda: now[0])
    hits = [{"key": "bucket", "now": value} for value in (100.0, 101.0, 102.0)]
    expected_hits = []
    for hit in hits:
        now[0] = hit["now"]
        allowed, retry_after = python_limiter.check(hit["key"])
        expected_hits.append({"allowed": allowed, "retry_after": retry_after})

    process = _rust({"operation": "rate", "hits": hits})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["results"] == expected_hits

    now[0] = 100.0
    python_cache = IdempotencyCache(clock=lambda: now[0])
    response = CachedResponse(200, b"ok", "text/plain")
    python_cache.put("cache-key", response)
    now[0] = 105.01
    expected = python_cache.get("cache-key")
    actions = [
        {
            "action": "put",
            "key": "cache-key",
            "now": 100.0,
            "response": {"status": 200, "body": "ok", "media_type": "text/plain"},
        },
        {"action": "get", "key": "cache-key", "now": 105.01},
    ]
    process = _rust({"operation": "cache", "actions": actions})
    assert process.returncode == 0, process.stderr
    results = json.loads(process.stdout)["results"]
    assert results[0] == {"cached": True}
    assert results[1] == {
        "response": None
        if expected is None
        else {
            "status": expected.status,
            "body": expected.body.decode(),
            "media_type": expected.media_type,
        }
    }


def _python_compute(request):
    import asyncio

    from agentrouter.server.limits import CachedResponse, IdempotencyCache

    cache = IdempotencyCache(ttl=request["ttl"])
    calls = {key: 0 for key in set(request["keys"])}
    response_data = request["response"]

    async def compute(key):
        try:
            async with cache.flight(key):
                cached = cache.get(key)
                if cached is not None:
                    return {
                        "response": {
                            "status": cached.status,
                            "body": cached.body.decode(),
                            "media_type": cached.media_type,
                        }
                    }
                calls[key] += 1
                if request["delay_ms"]:
                    await asyncio.sleep(request["delay_ms"] / 1000)
                if request["fail"]:
                    return {"error": "injected failure"}
                result = CachedResponse(
                    response_data["status"],
                    response_data["body"].encode(),
                    response_data["media_type"],
                )
                if 200 <= result.status < 300:
                    cache.put(key, result)
                return {
                    "response": {
                        "status": result.status,
                        "body": result.body.decode(),
                        "media_type": result.media_type,
                    }
                }
        finally:
            cache.release_flight(key)

    async def run():
        return await asyncio.gather(*(compute(key) for key in request["keys"]))

    results = asyncio.run(run())
    return {"calls": sum(calls.values()), "results": results}


@pytest.mark.parametrize(
    "keys,status,fail,expected_calls",
    [
        (["same"] * 8, 200, False, 1),
        (["same"] * 5, 422, False, 5),
        (["same"] * 4, 200, True, 4),
        (["a", "a", "b", "b"], 201, False, 2),
    ],
)
def test_rust_keyed_computation_matches_python_single_flight(keys, status, fail, expected_calls):
    request = {
        "operation": "compute",
        "ttl": 60,
        "now": 10.0,
        "keys": keys,
        "delay_ms": 5,
        "fail": fail,
        "response": {"status": status, "body": "shared", "media_type": "text/plain"},
    }
    expected = _python_compute(request)
    process = _rust(request)
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    assert actual == expected
    assert actual["calls"] == expected_calls
