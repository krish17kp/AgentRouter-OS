"""TASK-003 — Hypothesis property tests for core invariants (backlog L5).

Skips cleanly where the optional `property` extra (hypothesis) is absent, so the
default test env never hard-fails on a missing dev dependency.
"""

from __future__ import annotations

import json

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from agentrouter.classifier import DEFAULT_UNCERTAINTY_THRESHOLD, classify  # noqa: E402
from agentrouter.observability import route_decision_record  # noqa: E402
from agentrouter.schema import ApprovalLevel, Level, TaskType  # noqa: E402

# Independent literal of the expected risk->approval mapping. Deliberately NOT the
# classifier's own _APPROVAL table, so a corrupted table is actually caught.
EXPECTED_APPROVAL = {
    Level.low: ApprovalLevel.auto,
    Level.medium: ApprovalLevel.notify,
    Level.high: ApprovalLevel.human_approval_required,
}
from agentrouter.server.limits import (  # noqa: E402
    CachedResponse,
    IdempotencyCache,
    RateLimiter,
)

pytestmark = pytest.mark.property


class _FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def time(self) -> float:
        return self.t


# ---- classifier invariants ----


@given(task=st.text(max_size=200))
def test_classify_output_always_valid(task):
    c = classify(task)
    assert 0.0 <= c.confidence <= 1.0
    assert isinstance(c.task_type, TaskType)
    assert isinstance(c.risk, Level)
    assert c.context_tokens >= 0
    assert c.approval_level == EXPECTED_APPROVAL[c.risk]
    assert c.needs_clarification == (c.confidence < DEFAULT_UNCERTAINTY_THRESHOLD)


@given(task=st.text(max_size=200), risk=st.sampled_from(list(Level)))
def test_classify_explicit_risk_always_wins(task, risk):
    assert classify(task, risk=risk).risk == risk


@given(task=st.text(max_size=200))
def test_classify_is_deterministic(task):
    assert classify(task).model_dump() == classify(task).model_dump()


# ---- rate limiter invariant ----


@given(limit=st.integers(min_value=1, max_value=20), n=st.integers(min_value=0, max_value=100))
def test_rate_limiter_never_exceeds_limit(limit, n):
    # A huge window keeps every call inside one window.
    rl = RateLimiter(limit=limit, window=10_000, clock=_FakeClock().time)
    allowed = sum(1 for _ in range(n) if rl.check("k")[0])
    assert allowed == min(n, limit)


# ---- idempotency cache round-trip ----


@given(key=st.text(min_size=1, max_size=30), body=st.binary(max_size=200))
def test_idempotency_roundtrip_within_ttl(key, body):
    cache = IdempotencyCache(ttl=10_000, clock=_FakeClock().time)
    cache.put(key, CachedResponse(200, body, "application/json"))
    got = cache.get(key)
    assert got is not None and got.body == body and got.status == 200


# ---- observability privacy ----


@given(task=st.text(max_size=200))
def test_route_record_never_leaks_task_text(task):
    marked = "S3NT1NEL_" + task
    payload = {
        "classification": {"task_type": "coding", "risk": "low", "confidence": 0.9},
        "recommendation": {"model": "openai/gpt-x"},
        "gates": {"auto_execute_allowed": True},
    }
    rec = route_decision_record(task=marked, payload=payload)
    assert rec["task_len"] == len(marked)
    assert marked not in json.dumps(rec)  # metadata only; raw task never copied
