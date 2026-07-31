"""Mutation-hardening for safety.gates_for — the auto-execute policy gate.

Every branch and the exact checklist content are pinned so a flipped comparison,
a swapped boolean operator, or a mutated string is caught. High risk must NEVER
allow auto-execute regardless of approval level (ROUTING_RULES.md §4).
"""

from __future__ import annotations

from factories import make_classification

from agentrouter.safety import _CHECKLISTS, gates_for
from agentrouter.schema import ApprovalLevel, Level


def test_high_risk_never_auto_executes_even_when_approval_is_auto():
    gates = gates_for(make_classification(risk=Level.high, approval_level=ApprovalLevel.auto))
    assert gates["auto_execute_allowed"] is False


def test_low_risk_with_auto_approval_allows_auto_execute():
    gates = gates_for(make_classification(risk=Level.low, approval_level=ApprovalLevel.auto))
    assert gates["auto_execute_allowed"] is True


def test_medium_risk_with_auto_approval_allows_auto_execute():
    gates = gates_for(make_classification(risk=Level.medium, approval_level=ApprovalLevel.auto))
    assert gates["auto_execute_allowed"] is True


def test_low_risk_without_auto_approval_blocks_auto_execute():
    gates = gates_for(
        make_classification(risk=Level.low, approval_level=ApprovalLevel.notify)
    )
    assert gates["auto_execute_allowed"] is False


def test_human_approval_required_blocks_auto_execute():
    gates = gates_for(
        make_classification(
            risk=Level.low, approval_level=ApprovalLevel.human_approval_required
        )
    )
    assert gates["auto_execute_allowed"] is False


def test_checklist_matches_level_exactly_low():
    gates = gates_for(make_classification(risk=Level.low))
    assert gates["checklist"] == _CHECKLISTS[Level.low]
    assert gates["checklist"] == ["Sanity-check the output before using it"]


def test_checklist_matches_level_exactly_medium():
    gates = gates_for(make_classification(risk=Level.medium))
    assert gates["checklist"] == _CHECKLISTS[Level.medium]
    assert "Review the output before acting on it" in gates["checklist"]
    assert len(gates["checklist"]) == 3


def test_checklist_matches_level_exactly_high():
    gates = gates_for(make_classification(risk=Level.high))
    assert gates["checklist"] == _CHECKLISTS[Level.high]
    assert "Human sign-off (no auto-execute)" in gates["checklist"]
    assert len(gates["checklist"]) == 5


def test_checklist_is_a_copy_not_the_module_constant():
    gates = gates_for(make_classification(risk=Level.low))
    gates["checklist"].append("tampered")
    # mutating the returned list must not corrupt the shared constant
    assert "tampered" not in _CHECKLISTS[Level.low]


def test_approval_level_echoed_as_value_string():
    gates = gates_for(
        make_classification(approval_level=ApprovalLevel.human_approval_required)
    )
    assert gates["approval_level"] == "human-approval-required"


def test_returns_all_three_keys():
    gates = gates_for(make_classification())
    assert set(gates) == {"checklist", "auto_execute_allowed", "approval_level"}
