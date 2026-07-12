"""Storage layer — SQLite DecisionLog (ARCHITECTURE.md §2.11)."""

from __future__ import annotations

import getpass
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    payload TEXT NOT NULL,
    user TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL REFERENCES decisions(id),
    created_at TEXT NOT NULL,
    rating INTEGER,
    note TEXT
);
"""


def current_user() -> str:
    """M7 identity: AGENTROUTER_USER wins (shared-home teams), else the OS user."""
    return os.environ.get("AGENTROUTER_USER") or getpass.getuser()


def connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "agentrouter.db")
    conn.executescript(_SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
    if "user" not in cols:  # migrate pre-M7 DBs in place
        conn.execute("ALTER TABLE decisions ADD COLUMN user TEXT")
        conn.commit()
    return conn


def save_decision(conn: sqlite3.Connection, task: str, payload: dict) -> str:
    cur = conn.execute(
        "INSERT INTO decisions (created_at, task, payload, user) VALUES (?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), task, json.dumps(payload), current_user()),
    )
    conn.commit()
    return f"d_{cur.lastrowid:05d}"


def recent_ids(conn: sqlite3.Connection, n: int = 3) -> list[str]:
    rows = conn.execute("SELECT id FROM decisions ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [f"d_{r[0]:05d}" for r in rows]


def recent_decisions(conn: sqlite3.Connection, n: int = 20) -> list[dict]:
    """Newest-first summaries for stats/dashboard (id, time, task, pick, score, risk)."""
    rows = conn.execute(
        "SELECT id, created_at, task, payload, user FROM decisions ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    out = []
    for rowid, created_at, task, payload_json, user in rows:
        p = json.loads(payload_json)
        rec = p.get("recommendation") or {}
        out.append(
            {
                "decision_id": f"d_{rowid:05d}",
                "created_at": created_at,
                "task": task,
                "model": rec.get("model") or "(no eligible model)",
                "score": rec.get("score"),
                "risk": (p.get("classification") or {}).get("risk"),
                "user": user or "unknown",
            }
        )
    return out


def aggregate_stats(conn: sqlite3.Connection, tier_by_key: dict[str, str] | None = None) -> dict:
    """Telemetry aggregates: decision counts, risk/model/tier distributions, feedback."""
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    by_risk: dict[str, int] = {}
    by_model: dict[str, int] = {}
    by_user: dict[str, int] = {}
    for payload_json, user in conn.execute("SELECT payload, user FROM decisions"):
        p = json.loads(payload_json)
        risk = (p.get("classification") or {}).get("risk") or "unknown"
        by_risk[risk] = by_risk.get(risk, 0) + 1
        rec = p.get("recommendation") or {}
        model = rec.get("model") or "(no eligible model)"
        by_model[model] = by_model.get(model, 0) + 1
        u = user or "unknown"
        by_user[u] = by_user.get(u, 0) + 1
    by_tier: dict[str, int] = {}
    for model, n in by_model.items():
        tier = (tier_by_key or {}).get(model, "unknown")
        by_tier[tier] = by_tier.get(tier, 0) + n
    fb_total, fb_avg, fb_accepted = conn.execute(
        "SELECT COUNT(*), AVG(rating), COALESCE(SUM(rating >= 4), 0) "
        "FROM feedback WHERE rating IS NOT NULL"
    ).fetchone()
    return {
        "decisions": total,
        "by_risk": by_risk,
        "by_model": by_model,
        "by_pricing_tier": by_tier,
        "by_user": by_user,
        "feedback": {
            "count": fb_total,
            "avg_rating": round(fb_avg, 2) if fb_avg is not None else None,
            "acceptance_rate": round(fb_accepted / fb_total, 2) if fb_total else None,
        },
    }


def load_decision(conn: sqlite3.Connection, decision_id: str) -> dict | None:
    try:
        rowid = int(decision_id.removeprefix("d_"))
    except ValueError:
        return None
    row = conn.execute(
        "SELECT created_at, task, payload, user FROM decisions WHERE id = ?", (rowid,)
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[2])
    payload["created_at"] = row[0]
    payload["task"] = row[1]
    payload["decision_id"] = decision_id
    payload["user"] = row[3] or "unknown"
    return payload
