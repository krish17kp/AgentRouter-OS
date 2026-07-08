"""Testing-gap closure: classifier fuzz (seeded, stdlib) + fallback-chain edges."""

import random
import string

from agentrouter.classifier import classify
from agentrouter.engine import pick_fallback, route, score_models
from agentrouter.schema import (
    Ability,
    Classification,
    LatencyTier,
    ModelEntry,
    PricingTier,
)

# --- classifier fuzz ---------------------------------------------------------------

_VOCAB = (
    "refactor auth production summarize readme plan 300k tokens image run tests "
    "database simple entire codebase and write draft api migrate deploy secret"
).split()


def test_classifier_never_crashes_on_random_text():
    rng = random.Random(1234)  # seeded: reproducible, no flakes
    corpus = string.printable
    for _ in range(300):
        text = "".join(rng.choice(corpus) for _ in range(rng.randint(0, 200)))
        cls = classify(text)
        assert isinstance(cls, Classification)
        assert cls.context_tokens > 0


def test_classifier_never_crashes_on_random_vocab_combos():
    rng = random.Random(99)
    for _ in range(300):
        text = " ".join(rng.choice(_VOCAB) for _ in range(rng.randint(1, 30)))
        cls = classify(text)
        assert isinstance(cls, Classification)
        assert cls.approval_level is not None


# --- fallback-chain edges -------------------------------------------------------------


def _model(model_id, provider="openrouter", tier=PricingTier.medium, fallback=(), coding=7):
    return ModelEntry(
        provider=provider,
        model_id=model_id,
        context_window=100_000,
        max_output_tokens=8_000,
        pricing_tier=tier,
        latency_tier=LatencyTier.medium,
        ability=Ability(coding=coding, reasoning=5, writing=5),
        tool_support=[],
        vision_support=False,
        deprecation_status="active",
        fallback=list(fallback),
    )


_CLS = classify("fix a bug in the parser")  # coding / low risk / small context


def test_single_eligible_model_has_no_fallback():
    result = route([_model("only-one")], _CLS)
    assert result["recommendation"]["model_id"] == "only-one"
    assert result["fallback"] is None


def test_declared_fallback_wins_when_eligible():
    models = [
        _model("top", coding=9, fallback=["declared"]),
        _model("declared", coding=5),
        _model("better-scorer", coding=8),
    ]
    result = route(models, _CLS)
    assert result["recommendation"]["model_id"] == "top"
    assert result["fallback"]["model_id"] == "declared"  # declared beats higher-scoring


def test_unresolvable_declared_fallback_falls_through_to_rule_2():
    models = [
        _model("top", coding=9, fallback=["ghost-model"]),
        _model("other-provider", provider="openai", coding=8),
    ]
    result = route(models, _CLS)
    assert result["fallback"]["model_id"] == "other-provider"


def test_rule_2_prefers_cheaper_tier_same_provider():
    models = [
        _model("top", tier=PricingTier.high, coding=9),
        _model("same-tier-sibling", tier=PricingTier.high, coding=8),
        _model("cheaper-sibling", tier=PricingTier.low, coding=7),
    ]
    ranked = score_models(models, _CLS, {"w_cap": 1.0, "w_cost": 0, "w_lat": 0, "w_ctx": 0})
    by_key = {m.key: m for m in models}
    fb = pick_fallback(ranked, by_key, {m.model_id for m in models})
    assert fb["model_id"] == "cheaper-sibling"


def test_rule_3_any_second_best_when_nothing_differs():
    models = [
        _model("top", tier=PricingTier.high, coding=9),
        _model("twin", tier=PricingTier.high, coding=8),
    ]
    ranked = score_models(models, _CLS, {"w_cap": 1.0, "w_cost": 0, "w_lat": 0, "w_ctx": 0})
    by_key = {m.key: m for m in models}
    fb = pick_fallback(ranked, by_key, {m.model_id for m in models})
    assert fb["model_id"] == "twin"
