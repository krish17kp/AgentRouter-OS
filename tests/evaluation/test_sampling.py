"""Tests for deterministic sampling."""

from agentrouter.evaluation.sampling import deterministic_sample

_ITEMS = [f"item-{i}" for i in range(50)]


def _k(x):
    return x


def test_sample_is_deterministic_across_calls():
    a = deterministic_sample(_ITEMS, 10, seed=7, key=_k)
    b = deterministic_sample(_ITEMS, 10, seed=7, key=_k)
    assert a == b


def test_different_seed_changes_sample():
    a = deterministic_sample(_ITEMS, 10, seed=1, key=_k)
    b = deterministic_sample(_ITEMS, 10, seed=2, key=_k)
    assert a != b


def test_limit_zero_is_empty():
    assert deterministic_sample(_ITEMS, 0, seed=1, key=_k) == []


def test_limit_ge_len_returns_all():
    assert deterministic_sample(_ITEMS, 999, seed=1, key=_k) == _ITEMS


def test_sample_preserves_original_order():
    s = deterministic_sample(_ITEMS, 10, seed=3, key=_k)
    assert s == [x for x in _ITEMS if x in set(s)]
