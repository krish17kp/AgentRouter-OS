"""Phase 3 — routing benchmark over synthetic registries + routing invariants."""

from pathlib import Path

import pytest

from agentrouter import evaluate as ev
from agentrouter.engine import eligibility, route
from agentrouter.safety import gates_for
from agentrouter.schema import (
    Ability,
    Classification,
    ContextBand,
    DeprecationStatus,
    LatencyTier,
    Level,
    ModelEntry,
    OutputType,
    PricingTier,
    TaskType,
)


def test_routing_gold_all_scenarios_pass():
    report = ev.evaluate_routing(Path("benchmarks") / "routing_gold_v1.yaml")
    assert report["all_pass"], report["failures"]
    assert report["n_scenarios"] >= 10


# --- invariants (property / metamorphic) -------------------------------------


def _model(
    model_id,
    ctx=100_000,
    tools=(),
    vision=False,
    tier=PricingTier.medium,
    status=DeprecationStatus.active,
    coding=7,
):
    return ModelEntry(
        provider="p",
        model_id=model_id,
        context_window=ctx,
        max_output_tokens=8000,
        pricing_tier=tier,
        latency_tier=LatencyTier.medium,
        ability=Ability(coding=coding, reasoning=coding, writing=coding),
        tool_support=list(tools),
        vision_support=vision,
        deprecation_status=status,
    )


def _cls(context_tokens=4000, tools=(), risk=Level.low, approval=None):
    from agentrouter.classifier import _APPROVAL

    return Classification(
        task_type=TaskType.coding,
        complexity=Level.high,
        risk=risk,
        context_tokens=context_tokens,
        context_band=ContextBand.small,
        output_type=OutputType.code,
        tool_needs=list(tools),
        approval_level=approval or _APPROVAL[risk],
    )


_FLEET = [
    _model("a", ctx=50_000, tools=["file-edit"], coding=9),
    _model("b", ctx=200_000, tools=["file-edit", "shell"], vision=True, coding=8),
    _model("c", ctx=1_000_000, tools=[], coding=7),
    _model("d", ctx=8_000, tools=["file-edit", "shell"], coding=6),
]


@pytest.mark.parametrize("t1,t2", [(1_000, 100_000), (100_000, 500_000), (4_000, 2_000_000)])
def test_increasing_context_cannot_increase_eligible_count(t1, t2):
    lo = len(eligibility(_FLEET, _cls(context_tokens=min(t1, t2)))[0])
    hi = len(eligibility(_FLEET, _cls(context_tokens=max(t1, t2)))[0])
    assert hi <= lo


@pytest.mark.parametrize("extra", [["file-edit"], ["file-edit", "shell"], ["vision"]])
def test_adding_tools_cannot_increase_eligible_count(extra):
    base = len(eligibility(_FLEET, _cls(tools=[]))[0])
    more = len(eligibility(_FLEET, _cls(tools=extra))[0])
    assert more <= base


def test_increasing_risk_cannot_enable_execution():
    prev = True
    for risk in (Level.low, Level.medium, Level.high):
        allowed = gates_for(_cls(risk=risk))["auto_execute_allowed"]
        assert allowed <= prev  # monotonically non-increasing (True=1 >= False=0)
        prev = allowed
    # high risk always blocks
    assert gates_for(_cls(risk=Level.high))["auto_execute_allowed"] is False


def test_retired_models_never_win():
    models = [
        _model(
            "retired-super", tier=PricingTier.frontier, status=DeprecationStatus.retired, coding=10
        ),
        _model("active-ok", coding=5),
    ]
    r = route(models, _cls())
    assert r["recommendation"]["model_id"] == "active-ok"
    assert all(row["model_id"] != "retired-super" for row in r["scores"])


@pytest.mark.parametrize("cap", list(PricingTier))
def test_pricing_cap_never_exceeded(cap):
    order = [t.value for t in PricingTier]
    ceiling = order.index(cap.value)
    fleet = [_model(f"m-{t.value}", tier=t, coding=8) for t in PricingTier]
    capped = [m for m in fleet if order.index(m.pricing_tier.value) <= ceiling]
    r = route(capped, _cls())
    if r["recommendation"] is not None:
        won = order.index(r["recommendation"]["pricing_tier"])
        assert won <= ceiling


def test_more_models_cannot_shrink_eligible_set():
    """Metamorphic: adding a model never removes an already-eligible one."""
    cls = _cls(context_tokens=4000)
    small = eligibility(_FLEET[:2], cls)[0]
    big = eligibility(_FLEET, cls)[0]
    small_ids = {m.model_id for m in small}
    big_ids = {m.model_id for m in big}
    assert small_ids <= big_ids
