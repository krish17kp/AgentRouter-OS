"""SQLite initialization must serialize schema upgrades across connections."""

from __future__ import annotations

import concurrent.futures
import sqlite3
import threading

from agentrouter import store


def test_concurrent_connections_upgrade_legacy_schema_once(tmp_path):
    home = tmp_path / "shared-home"
    home.mkdir()
    with sqlite3.connect(home / "agentrouter.db") as database:
        database.execute(
            "CREATE TABLE decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "created_at TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        database.execute(
            "CREATE TABLE feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "decision_id INTEGER NOT NULL, created_at TEXT NOT NULL, rating INTEGER, note TEXT)"
        )

    workers = 16
    start = threading.Barrier(workers)

    def initialize(_index: int) -> bool:
        start.wait()
        connection = store.connect(home)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(decisions)")}
            return "user" in columns
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(initialize, range(workers)))
