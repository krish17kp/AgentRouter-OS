"""SafetyEngine — risk -> checklist + gates (ROUTING_RULES.md §4, NFR-8)."""

from __future__ import annotations

from .schema import ApprovalLevel, Classification, Level

_CHECKLISTS = {
    Level.low: [
        "Sanity-check the output before using it",
    ],
    Level.medium: [
        "Review the output before acting on it",
        "Run relevant tests / verify behavior",
        "Confirm the change stays within intended scope",
    ],
    Level.high: [
        "Review full diff before applying",
        "Run the test suite",
        "Secret scan changed files",
        "Confirm rollback path",
        "Human sign-off (no auto-execute)",
    ],
}


def gates_for(classification: Classification) -> dict:
    """Returns checklist + gating flags. High risk never allows auto-execute."""
    risk = classification.risk
    return {
        "checklist": list(_CHECKLISTS[risk]),
        "auto_execute_allowed": risk is not Level.high
        and classification.approval_level is ApprovalLevel.auto,
        "approval_level": classification.approval_level.value,
    }
