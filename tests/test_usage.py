"""Usage/quota intelligence (Production Milestone 1).

No real provider has a registered live check today (P2 in BACKLOG.yaml is
credential-gated), so these tests prove the *mechanism* — default/unknown,
unsupported-by-default, isolation of a failing/slow provider, and quota-aware
re-ranking in `route` — using a fake adapter registered and torn down per
test. No network call is ever made.
"""

from __future__ import annotations

import time

import pytest

from agentrouter import usage
from agentrouter.classifier import classify
from agentrouter.engine import BASE_WEIGHTS
from agentrouter.engine import route as engine_route
from agentrouter.schema import Ability, LatencyTier, ModelEntry, PricingTier


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts with no live checks registered (production default)."""
    usage._LIVE_CHECKS.clear()
    yield
    usage._LIVE_CHECKS.clear()


def _model(model_id: str, provider: str) -> ModelEntry:
    return ModelEntry(
        provider=provider,
        model_id=model_id,
        context_window=100_000,
        max_output_tokens=8_000,
        pricing_tier=PricingTier.medium,
        latency_tier=LatencyTier.medium,
        ability=Ability(coding=7, reasoning=7, writing=7),
        tool_support=[],
        vision_support=False,
        deprecation_status="active",
    )


# --- check_usage: default/unsupported/isolation ------------------------------


def test_default_is_unknown_no_network_no_live_flag():
    status = usage.check_usage("openai-api")
    assert status.state == usage.UNKNOWN
    assert status.source == "none"


def test_live_with_no_registered_adapter_is_unsupported():
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.UNSUPPORTED
    assert status.remaining is None
    assert status.reset_at is None


def test_live_check_never_fabricates_a_number():
    status = usage.check_usage("anthropic-api", live=True)
    assert status.remaining is None
    assert status.reset_at is None


def test_a_registered_check_that_raises_is_isolated_as_error_not_propagated():
    def boom(timeout: float) -> usage.UsageStatus:
        raise TimeoutError("simulated network timeout")

    usage.register_live_check("openai-api", boom)
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.ERROR
    assert "TimeoutError" in status.detail


def test_a_registered_check_returning_garbage_is_isolated_as_error():
    usage.register_live_check("openai-api", lambda timeout: "not a UsageStatus")
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.ERROR


def test_a_slow_check_is_bounded_by_timeout_not_left_to_hang():
    """The CLI help promises 'bounded timeout' — a check that ignores its own
    `timeout` argument must still not block the caller past it."""

    def slow(timeout: float) -> usage.UsageStatus:
        time.sleep(2.0)  # deliberately ignores the timeout argument it was given
        return usage.UsageStatus("openai-api", usage.AVAILABLE, "eventually fine")

    usage.register_live_check("openai-api", slow)
    started = time.monotonic()
    status = usage.check_usage("openai-api", live=True, timeout=0.2)
    elapsed = time.monotonic() - started
    assert status.state == usage.ERROR
    assert "0.2s timeout" in status.detail
    assert elapsed < 1.0, f"check_usage blocked for {elapsed}s despite a 0.2s timeout"


def test_a_fast_raise_is_reported_as_the_adapters_error_not_a_timeout():
    """A `TimeoutError` the adapter itself raises (e.g. its own HTTP client did)
    must be reported as the adapter's failure, not confused with our own
    wall-clock timeout — concurrent.futures.TimeoutError is the same class as
    the builtin TimeoutError as of Python 3.11, so this is a real ambiguity
    the implementation must resolve correctly."""

    def raises_immediately(timeout: float) -> usage.UsageStatus:
        raise TimeoutError("the adapter's own HTTP client timed out")

    usage.register_live_check("openai-api", raises_immediately)
    status = usage.check_usage("openai-api", live=True, timeout=5.0)
    assert status.state == usage.ERROR
    assert "TimeoutError" in status.detail
    assert "exceeded the 5.0s timeout" not in status.detail


def test_a_registered_check_can_report_available_with_real_evidence():
    def fake(timeout: float) -> usage.UsageStatus:
        return usage.UsageStatus(
            "openai-api",
            usage.AVAILABLE,
            "12000 of 50000 used",
            remaining=38000.0,
            checked_at=time.time(),
            source="live",
        )

    usage.register_live_check("openai-api", fake)
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.AVAILABLE
    assert status.remaining == 38000.0


def test_a_registered_check_can_report_exhausted():
    usage.register_live_check(
        "openai-api",
        lambda t: usage.UsageStatus("openai-api", usage.EXHAUSTED, "0 remaining", remaining=0.0),
    )
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.EXHAUSTED


def test_unregister_restores_unsupported():
    usage.register_live_check(
        "openai-api", lambda t: usage.UsageStatus("openai-api", usage.AVAILABLE, "ok")
    )
    usage.unregister_live_check("openai-api")
    status = usage.check_usage("openai-api", live=True)
    assert status.state == usage.UNSUPPORTED


def test_a_registered_check_cannot_inject_control_characters_or_ansi_escapes():
    """A live check is untrusted provider output — the same class of risk
    hosts._sanitize guards against for CLI hosts."""
    hostile = "quota ok\x1b[2K\rFAKE: all systems nominal\x00" + ("x" * 500)
    usage.register_live_check(
        "openai-api", lambda t: usage.UsageStatus("openai-api", usage.AVAILABLE, hostile)
    )
    status = usage.check_usage("openai-api", live=True)
    assert "\x1b" not in status.detail
    assert "\x00" not in status.detail
    assert len(status.detail) <= 200


def test_as_dict_is_json_serializable_shape():
    status = usage.check_usage("openai-api")
    d = status.as_dict()
    assert set(d) == {
        "provider",
        "state",
        "detail",
        "remaining",
        "reset_at",
        "checked_at",
        "source",
    }


# --- apply_live_verification: re-ranking in route() ---------------------------


def _route_setup():
    models = [_model("gpt", "openai"), _model("claude", "anthropic")]
    cls = classify("write a small script", tools=[])
    result = engine_route(models, cls, BASE_WEIGHTS)
    return models, cls, result


def test_apply_live_verification_is_noop_when_not_exhausted():
    models, cls, result = _route_setup()
    models_by_key = {m.key: m for m in models}
    out = usage.apply_live_verification(result, models, models_by_key, cls, BASE_WEIGHTS, None)
    assert out["recommendation"]["model"] == result["recommendation"]["model"]
    assert out["usage_check"]["state"] == usage.UNSUPPORTED


def test_apply_live_verification_reranks_away_an_exhausted_top_pick():
    models, cls, result = _route_setup()
    models_by_key = {m.key: m for m in models}
    top_provider = models_by_key[result["recommendation"]["model"]].provider

    usage.register_live_check(
        top_provider,
        lambda t: usage.UsageStatus(top_provider, usage.EXHAUSTED, "no budget left", remaining=0.0),
    )
    out = usage.apply_live_verification(result, models, models_by_key, cls, BASE_WEIGHTS, None)

    assert out["recommendation"]["model"] != result["recommendation"]["model"]
    assert any("quota exhausted" in e["reason"] for e in out["excluded"])
    assert any("quota exhausted" in s for s in out["weight_shifts"])
    assert out["usage_check"]["state"] == usage.EXHAUSTED


def test_apply_live_verification_does_not_duplicate_eligibility_exclusions():
    """Regression: retry['excluded'] used to be concatenated on top of the
    original result's excluded list, duplicating every eligibility drop that
    isn't specific to the exhausted top pick."""
    models = [
        _model("gpt", "openai"),
        _model("claude", "anthropic"),
        _model("tiny-context", "other"),
    ]
    models[2] = models[2].model_copy(update={"context_window": 1})  # always eligibility-excluded
    cls = classify("write a small script", tools=[], context_tokens=50_000)
    result = engine_route(models, cls, BASE_WEIGHTS)
    models_by_key = {m.key: m for m in models}
    top_provider = models_by_key[result["recommendation"]["model"]].provider

    usage.register_live_check(
        top_provider, lambda t: usage.UsageStatus(top_provider, usage.EXHAUSTED, "none left")
    )
    out = usage.apply_live_verification(result, models, models_by_key, cls, BASE_WEIGHTS, None)

    reasons = [e["model"] for e in out["excluded"]]
    assert len(reasons) == len(set(reasons)), f"duplicated exclusion entries: {reasons}"


def test_apply_live_verification_with_no_recommendation_is_untouched():
    empty_result = {"recommendation": None, "excluded": [], "weight_shifts": [], "scores": []}
    out = usage.apply_live_verification(empty_result, [], {}, None, BASE_WEIGHTS, None)
    assert out is empty_result
