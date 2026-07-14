"""Tests for the dataset registry and profiles."""

import pytest

from agentrouter.evaluation.registry import (
    PROFILES,
    dataset_names,
    get_adapter,
    profile_datasets,
)


def test_all_eight_datasets_registered():
    names = dataset_names()
    assert len(names) == 8
    assert "agentrouter-gold" in names


def test_profiles_reference_known_datasets():
    known = set(dataset_names())
    for profile, names in PROFILES.items():
        assert set(names) <= known, profile


def test_fast_profile_is_offline_gold_only():
    assert profile_datasets("fast") == ["agentrouter-gold"]


def test_unknown_dataset_raises():
    with pytest.raises(KeyError):
        get_adapter("does-not-exist")


def test_unknown_profile_raises():
    with pytest.raises(KeyError):
        profile_datasets("nope")


def test_gold_adapter_loads():
    adapter = get_adapter("agentrouter-gold")
    cases = adapter.load()
    assert len(cases) >= 150
