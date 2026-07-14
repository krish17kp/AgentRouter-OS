"""Tests for the AgentRouter gold adapter (§5.1)."""

from agentrouter.evaluation.adapters.agentrouter_gold import AgentRouterGoldAdapter
from agentrouter.evaluation.base import Availability
from agentrouter.evaluation.schema import ApprovalLevel
from agentrouter.schema import Level


def test_loads_all_gold_cases():
    cases = AgentRouterGoldAdapter().load()
    assert len(cases) >= 150


def test_availability_ready():
    assert AgentRouterGoldAdapter().availability() == Availability.READY


def test_approval_derived_from_risk():
    cases = {c.id: c for c in AgentRouterGoldAdapter().load()}
    payment = cases["cod-001"]  # risk high -> approval human-approval-required
    assert payment.expected.risks == [Level.high]
    assert ApprovalLevel.human_approval_required in payment.expected.approval_levels


def test_checksum_is_deterministic():
    a = AgentRouterGoldAdapter()
    assert a.checksum() == a.checksum()


def test_sampling_is_deterministic():
    a = AgentRouterGoldAdapter()
    s1 = [c.id for c in a.sample(limit=20, seed=5)]
    s2 = [c.id for c in a.sample(limit=20, seed=5)]
    assert s1 == s2 and len(s1) == 20


def test_payment_case_is_high_risk_coding():
    cases = {c.id: c for c in AgentRouterGoldAdapter().load()}
    payment = cases["cod-001"]
    tt = [t.value for t in payment.expected.task_types]
    assert "coding" in tt
