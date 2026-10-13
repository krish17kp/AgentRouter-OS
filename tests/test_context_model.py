"""Tests for the learned context-band model + its safe rule fallback (TASK-009)."""

from agentrouter import classifier, context_model
from agentrouter.context_model import CLASSES, FEATURES, feature_vector, load_model


def test_feature_vector_is_deterministic_and_sized():
    p = "Refactor the billing subsystem already in use."
    assert feature_vector(p) == feature_vector(p)
    assert len(feature_vector(p)) == len(FEATURES)
    assert all(v in (0.0, 1.0) for v in feature_vector(p))


def test_packaged_model_loads_and_predicts():
    m = load_model()
    assert m is not None, "trained artifact must ship in the wheel"
    band, conf = m.predict("Audit 120000 tokens of access-control traces.")
    assert band in CLASSES
    assert 0.0 <= conf <= 1.0
    assert band == "large"  # explicit large-token cue


def test_model_matches_feature_extractor_shape():
    m = load_model()
    assert m.features == FEATURES
    assert m.classes == CLASSES
    assert len(m.coef) == len(CLASSES) and all(len(r) == len(FEATURES) for r in m.coef)


def test_classify_uses_rules_when_learned_disabled():
    # Shipped default: learned band is OFF, so classify == rule estimator.
    assert classifier._USE_LEARNED_BAND is False
    for prompt in (
        "Return the larger of two integers.",
        "Refactor the billing subsystem already in use.",
        "Summarize a 96k-token compliance archive.",
    ):
        cls = classifier.classify(prompt)
        rules_tokens = classifier._context_tokens(prompt.lower(), cls.task_type)
        assert cls.context_band == classifier._band(rules_tokens)


def test_explicit_context_tokens_wins():
    cls = classifier.classify("do something", context_tokens=90_000)
    assert cls.context_tokens == 90_000
    assert cls.context_band.value == "large"


def test_missing_model_falls_back(monkeypatch):
    monkeypatch.setattr(classifier, "_USE_LEARNED_BAND", True)
    monkeypatch.setattr(context_model, "load_model", lambda: None)
    # still resolves via rules, no crash
    cls = classifier.classify("Refactor the billing subsystem already in use.")
    assert cls.context_band.value in {"small", "medium", "large"}


def test_malformed_model_returns_none(monkeypatch, tmp_path):
    # Contract: any load/parse/validate error -> None (caller falls back to rules).
    import json as _json
    from importlib import resources

    class _FakeRes:
        def __truediv__(self, _name):
            return self

        def read_text(self, **_kw):
            return _json.dumps(["not", "an", "object"])  # non-dict -> TypeError in _validate

    load_model.cache_clear()
    monkeypatch.setattr(resources, "files", lambda _pkg: _FakeRes())
    assert load_model() is None
    load_model.cache_clear()
