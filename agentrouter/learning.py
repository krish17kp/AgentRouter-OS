"""M4 feedback learning — bounded weight adaptation from stored ratings.

Design: deterministic recompute from the feedback table on every route, no
stored weight state. That makes every adaptation reversible by construction
(delete feedback rows, or set `learning: false` in config.yaml, and weights
revert to base). Interpretation: low ratings (<=2) mean the picked model
under-delivered, so shift emphasis from cost toward capability — in small,
clamped steps, only once a minimum sample exists.
"""

from __future__ import annotations

import sqlite3

MIN_FEEDBACK = 3  # no adaptation below this sample size (avoids overfitting to noise)
STEP = 0.01  # weight moved from w_cost to w_cap per negative rating
MAX_SHIFT = 0.10  # total shift cap
MIN_W_COST = 0.05  # cost never stops mattering entirely
NEGATIVE_AT_OR_BELOW = 2  # ratings 1-2 count as negative signals


def learned_weights(
    conn: sqlite3.Connection, base: dict[str, float]
) -> tuple[dict[str, float], str | None]:
    """Return (adapted weights, human-readable note) — note is None when nothing changed."""
    total, negative = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(rating <= ?), 0) FROM feedback WHERE rating IS NOT NULL",
        (NEGATIVE_AT_OR_BELOW,),
    ).fetchone()
    if total < MIN_FEEDBACK or not negative:
        return dict(base), None
    shift = min(STEP * negative, MAX_SHIFT, base["w_cost"] - MIN_W_COST)
    if shift <= 0:
        return dict(base), None
    w = {
        **base,
        "w_cap": round(base["w_cap"] + shift, 4),
        "w_cost": round(base["w_cost"] - shift, 4),
    }
    note = (
        f"learned from {total} rating(s), {negative} negative -> "
        f"w_cap +{shift:.2f}, w_cost -{shift:.2f} (delete feedback or set "
        f"learning: false to revert)"
    )
    return w, note
