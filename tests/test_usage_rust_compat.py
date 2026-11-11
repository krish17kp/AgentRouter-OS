"""Differential checks for Python and Rust quota-aware routing behavior."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from agentrouter import usage
from agentrouter.classifier import classify
from agentrouter.engine import BASE_WEIGHTS, route
from agentrouter.schema import Ability, LatencyTier, ModelEntry, PricingTier

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


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


def _rust_apply(models, classification, status) -> dict:
    request = {
        "models": [model.model_dump(mode="json") for model in models],
        "classification": classification.model_dump(mode="json"),
        "usage_check": status.as_dict(),
        "preference": None,
    }
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "usage_route_from_json"],
        cwd="rust/agentrouter-usage",
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "state", [usage.UNSUPPORTED, usage.AVAILABLE, usage.ERROR, usage.EXHAUSTED]
)
@pytest.mark.parametrize("detail", ["quota\x1b result", "a\u00a0b\u200bc\u2028d\ue000e"])
def test_usage_reranking_matches_python_contract(state, detail):
    models = [_model("gpt", "openai"), _model("claude", "anthropic")]
    classification = classify("write a small script", tools=[])
    original = route(models, classification)
    top = {model.key: model for model in models}[original["recommendation"]["model"]]
    status = usage.UsageStatus(
        provider=top.provider,
        state=state,
        detail=detail,
        remaining=0.0 if state == usage.EXHAUSTED else None,
        checked_at=123.0 if state != usage.UNSUPPORTED else None,
        source="none" if state == usage.UNSUPPORTED else "live",
    )
    usage.register_live_check(top.provider, lambda _timeout: status)
    try:
        expected = usage.apply_live_verification(
            original,
            models,
            {model.key: model for model in models},
            classification,
            BASE_WEIGHTS,
            None,
        )
    finally:
        usage.unregister_live_check(top.provider)

    assert _rust_apply(models, classification, status) == expected


def test_no_recommendation_matches_python_without_usage_annotation():
    models = []
    classification = classify("write a small script", tools=[])
    original = route(models, classification)
    status = usage.UsageStatus("unused", usage.UNSUPPORTED, "unused")
    expected = usage.apply_live_verification(
        original, models, {}, classification, BASE_WEIGHTS, None
    )
    assert _rust_apply(models, classification, status) == expected
