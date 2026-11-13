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


def test_concurrent_decision_writes_are_serialized_and_unique(tmp_path):
    home = tmp_path / "shared-home"
    workers = 8
    writes_per_worker = 8
    start = threading.Barrier(workers)

    def write_batch(worker: int) -> list[str]:
        start.wait()
        connection = store.connect(home)
        try:
            return [
                store.save_decision(
                    connection,
                    f"worker {worker} write {write}",
                    {"worker": worker, "write": write},
                )
                for write in range(writes_per_worker)
            ]
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        ids = [
            decision_id for batch in pool.map(write_batch, range(workers)) for decision_id in batch
        ]

    assert len(ids) == workers * writes_per_worker
    assert len(set(ids)) == len(ids)
    connection = store.connect(home)
    try:
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == len(ids)
    finally:
        connection.close()
