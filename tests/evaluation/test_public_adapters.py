"""Shared + dataset-specific tests for the 7 public/external adapters.

The generic contract (loads, availability, unique ids, deterministic checksum
and sampling, describe keys) is parametrized; the dataset-specific behaviours
(banking risk calibration, MASSIVE language filter, LongBench buckets,
LLMRouterBench mapping, external SKIPPED_EXTERNAL) get their own tests.
"""

import pytest

from agentrouter.evaluation.adapters.banking77 import Banking77Adapter
from agentrouter.evaluation.adapters.clinc150 import CLINC150Adapter
from agentrouter.evaluation.adapters.llmrouterbench import LLMRouterBenchAdapter
from agentrouter.evaluation.adapters.longbench_v2 import (
    CONTEXT_BUCKETS,
    LongBenchV2Adapter,
    bucket_for,
)
from agentrouter.evaluation.adapters.massive import MassiveAdapter
from agentrouter.evaluation.adapters.swebench import SWEBenchAdapter
from agentrouter.evaluation.adapters.twinrouterbench import TwinRouterBenchAdapter
from agentrouter.evaluation.base import Availability

_ALL = [
    CLINC150Adapter,
    Banking77Adapter,
    MassiveAdapter,
    LongBenchV2Adapter,
    SWEBenchAdapter,
    LLMRouterBenchAdapter,
    TwinRouterBenchAdapter,
]
_EXTERNAL = [LongBenchV2Adapter, SWEBenchAdapter, LLMRouterBenchAdapter, TwinRouterBenchAdapter]


@pytest.mark.parametrize("cls", _ALL, ids=lambda c: c.__name__)
def test_adapter_loads_from_fixture(cls):
    cases = cls().load()
    assert len(cases) >= 6
    assert cls().availability() == Availability.FIXTURE_ONLY


@pytest.mark.parametrize("cls", _ALL, ids=lambda c: c.__name__)
def test_ids_unique(cls):
    ids = [c.id for c in cls().load()]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("cls", _ALL, ids=lambda c: c.__name__)
def test_checksum_deterministic(cls):
    a = cls()
    assert a.checksum() == a.checksum()


@pytest.mark.parametrize("cls", _ALL, ids=lambda c: c.__name__)
def test_sampling_deterministic(cls):
    a = cls()
    assert [c.id for c in a.sample(limit=4, seed=3)] == [c.id for c in a.sample(limit=4, seed=3)]


@pytest.mark.parametrize("cls", _ALL, ids=lambda c: c.__name__)
def test_describe_has_keys(cls):
    d = cls().describe()
    assert {"name", "version", "license", "availability"} <= set(d)


@pytest.mark.parametrize("cls", _EXTERNAL, ids=lambda c: c.__name__)
def test_external_full_run_is_skipped(cls):
    status = cls().full_run_status()
    assert status["status"] == "SKIPPED_EXTERNAL"
    assert status["commands"]


# --- dataset-specific --------------------------------------------------------


def test_banking_risk_calibration():
    """Not every banking sentence is high risk (§5.7)."""
    cases = {c.task: c for c in Banking77Adapter().load()}
    low = "Explain why my card payment failed"
    high = "Change production card-payment authorization logic"
    assert [r.value for r in cases[low].expected.risks] == ["low"]
    assert [r.value for r in cases[high].expected.risks] == ["high"]


def test_massive_language_filter():
    assert {c.language for c in MassiveAdapter(languages=["en"]).load()} == {"en"}
    assert {c.language for c in MassiveAdapter(languages=["en", "hi"]).load()} == {"en", "hi"}


def test_massive_has_hindi():
    assert any(c.language == "hi" for c in MassiveAdapter().load())


def test_longbench_bucket_for():
    assert bucket_for(3_000) == "under-8k"
    assert bucket_for(20_000) == "8k-32k"
    assert bucket_for(100_000) == "32k-128k"
    assert bucket_for(300_000) == "128k-512k"
    assert bucket_for(700_000) == "over-512k"
    assert len(CONTEXT_BUCKETS) == 5


def test_llmrouterbench_requires_model_mapping():
    assert LLMRouterBenchAdapter().model_mapping_required() is True


def test_clinc_has_out_of_scope():
    cases = CLINC150Adapter().load()
    assert any("out-of-scope" in c.tags or c.domain == "oos" for c in cases)
