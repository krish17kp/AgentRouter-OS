"""Feedback storage evaluator (§7 feedback_storage, weight 7).

Round-trips a decision through the SQLite store in a throwaway temp home
(never the user's real ~/.agentrouter): save -> load -> field match, plus a
feedback row and stats aggregation. Score = 1.0 iff every step holds, else 0.0.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ...store import aggregate_stats, connect, load_decision, save_decision

_SAMPLE_PAYLOAD = {
    "classification": {"risk": "high"},
    "recommendation": {"model": "anthropic/claude-opus-4-8", "score": 0.87},
}


def evaluate_feedback() -> dict:
    """1.0 iff a decision + feedback round-trips and stats aggregate correctly."""
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / ".agentrouter"
        conn = connect(home)
        try:
            decision_id = save_decision(conn, "deploy to production", _SAMPLE_PAYLOAD)
            loaded = load_decision(conn, decision_id)
            checks["decision_saved"] = decision_id.startswith("d_")
            checks["decision_loaded"] = loaded is not None
            checks["task_roundtrip"] = bool(loaded and loaded["task"] == "deploy to production")
            checks["recommendation_roundtrip"] = bool(
                loaded and loaded["recommendation"]["model"] == "anthropic/claude-opus-4-8"
            )

            conn.execute(
                "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (?,?,?,?)",
                (1, datetime.now(timezone.utc).isoformat(), 5, "great"),
            )
            conn.commit()

            stats = aggregate_stats(conn)
            checks["stats_decision_count"] = stats["decisions"] == 1
            checks["stats_by_risk"] = stats["by_risk"].get("high") == 1
            checks["stats_feedback_count"] = stats["feedback"]["count"] == 1
        finally:
            conn.close()

    score = 1.0 if all(checks.values()) else 0.0
    return {"score": score, "detail": {"checks": checks}}
