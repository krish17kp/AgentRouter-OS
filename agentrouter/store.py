"""Storage layer — SQLite DecisionLog (ARCHITECTURE.md §2.11)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL REFERENCES decisions(id),
    created_at TEXT NOT NULL,
    rating INTEGER,
    note TEXT
);
"""


def connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "agentrouter.db")
    conn.executescript(_SCHEMA)
    return conn


def save_decision(conn: sqlite3.Connection, task: str, payload: dict) -> str:
    cur = conn.execute(
        "INSERT INTO decisions (created_at, task, payload) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), task, json.dumps(payload)),
    )
    conn.commit()
    return f"d_{cur.lastrowid:05d}"


def recent_ids(conn: sqlite3.Connection, n: int = 3) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM decisions ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    return [f"d_{r[0]:05d}" for r in rows]


def load_decision(conn: sqlite3.Connection, decision_id: str) -> dict | None:
    try:
        rowid = int(decision_id.removeprefix("d_"))
    except ValueError:
        return None
    row = conn.execute(
        "SELECT created_at, task, payload FROM decisions WHERE id = ?", (rowid,)
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[2])
    payload["created_at"] = row[0]
    payload["task"] = row[1]
    payload["decision_id"] = decision_id
    return payload
