"""Python/Rust `store.py` compatibility check for the R4 milestone.

Python writes decisions into a real SQLite file (release-gate authority),
then both Python's `agentrouter.store` reads and the Rust `agentrouter-storage`
port (via the `store_cli` bin) read that same file, asserting the read-side
query results (recent ids, recent-decisions summaries, aggregate stats,
single-decision load) match field-for-field.

Skips (does not fail) when `cargo` isn't on PATH, matching the other
Rust compatibility tests' convention.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess

import pytest

from agentrouter import store

RUST_CRATE_DIR = "rust/agentrouter-storage"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _run(home, *args) -> str:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "store_cli", "--", str(home), *args],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def seeded_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_USER", "compat-test-user")
    home = tmp_path / "home"
    conn = store.connect(home)
    store.save_decision(
        conn,
        "write a function",
        {"recommendation": {"model": "m1", "score": 0.9}, "classification": {"risk": "low"}},
    )
    store.save_decision(
        conn,
        "review a PR",
        {"recommendation": {"model": "m2", "score": 0.7}, "classification": {"risk": "medium"}},
    )
    store.save_decision(conn, "no eligible model task", {})
    conn.close()
    return home


def test_recent_ids_match(seeded_home):
    python_ids = store.recent_ids(store.connect(seeded_home), 2)
    rust_ids = json.loads(_run(seeded_home, "recent-ids", "2"))
    assert rust_ids == python_ids


def test_recent_decisions_match(seeded_home):
    python_decisions = store.recent_decisions(store.connect(seeded_home), 10)
    rust_decisions = json.loads(_run(seeded_home, "recent-decisions", "10"))
    assert rust_decisions == python_decisions


def test_aggregate_stats_match(seeded_home):
    conn = store.connect(seeded_home)
    conn.executemany(
        "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (?, ?, ?, ?)",
        [(1, "now", rating, "sample") for rating in [4, 3, 3, 3, 3, 3, 3, 3]],
    )
    conn.commit()
    python_stats = store.aggregate_stats(conn)
    rust_stats = json.loads(_run(seeded_home, "aggregate-stats"))
    assert rust_stats == python_stats
    assert rust_stats["feedback"]["avg_rating"] == 3.12
    assert rust_stats["feedback"]["acceptance_rate"] == 0.12


def test_aggregate_stats_match_with_pricing_tier_map(seeded_home):
    conn = store.connect(seeded_home)
    tier_by_key = {"m1": "fast", "m2": "budget"}
    python_stats = store.aggregate_stats(conn, tier_by_key)
    rust_stats = json.loads(_run(seeded_home, "aggregate-stats", json.dumps(tier_by_key)))
    assert rust_stats == python_stats
    assert rust_stats["by_pricing_tier"] == {"fast": 1, "budget": 1, "unknown": 1}
    conn.close()


def test_load_decision_matches(seeded_home):
    [first_id] = store.recent_ids(store.connect(seeded_home), 1)
    python_decision = store.load_decision(store.connect(seeded_home), first_id)
    rust_decision = json.loads(_run(seeded_home, "load", first_id))
    assert rust_decision == python_decision


def test_load_unknown_decision_matches(seeded_home):
    python_decision = store.load_decision(store.connect(seeded_home), "d_99999")
    rust_decision = json.loads(_run(seeded_home, "load", "d_99999"))
    assert rust_decision == python_decision


@pytest.mark.parametrize("decision_id", ["1", "d_1", "+1", " 1 ", "d_0_01"])
def test_load_python_integer_id_forms_match(seeded_home, decision_id):
    conn = store.connect(seeded_home)
    python_decision = store.load_decision(conn, decision_id)
    rust_decision = json.loads(_run(seeded_home, "load", decision_id))
    assert rust_decision == python_decision
    conn.close()


@pytest.mark.parametrize("decision_id", ["", "_1", "1_", "d__1", "1.0"])
def test_load_invalid_python_integer_id_forms_match(seeded_home, decision_id):
    conn = store.connect(seeded_home)
    python_decision = store.load_decision(conn, decision_id)
    rust_decision = json.loads(_run(seeded_home, "load", decision_id))
    assert rust_decision == python_decision
    conn.close()


def test_rust_saved_decision_matches_python_reader(seeded_home):
    conn = store.connect(seeded_home)
    payload = {
        "recommendation": {"model": "m-🌱", "score": 0.93},
        "classification": {"risk": "low"},
    }
    decision_id = json.loads(_run(seeded_home, "save", "réviser le dépôt", json.dumps(payload)))

    python_decision = store.load_decision(conn, decision_id)
    rust_decision = json.loads(_run(seeded_home, "load", decision_id))
    assert rust_decision == python_decision
    assert python_decision["task"] == "réviser le dépôt"
    assert python_decision["recommendation"]["model"] == "m-🌱"
    assert python_decision["user"] == "compat-test-user"
    conn.close()


def test_rust_snapshot_is_readable_by_python_and_creates_parent(seeded_home, tmp_path):
    destination = tmp_path / "nested" / "snapshot.db"
    assert json.loads(_run(seeded_home, "snapshot", str(destination))) is True

    conn = sqlite3.connect(destination)
    try:
        assert store.recent_ids(conn, 10) == ["d_00003", "d_00002", "d_00001"]
        assert store.aggregate_stats(conn)["decisions"] == 3
    finally:
        conn.close()

    python_snapshot = tmp_path / "python-snapshot" / "agentrouter.db"
    store.snapshot(seeded_home, python_snapshot)
    rust_ids = json.loads(_run(python_snapshot.parent, "recent-ids", "10"))
    assert rust_ids == ["d_00003", "d_00002", "d_00001"]


def test_malformed_persisted_json_fails_closed_in_both_runtimes(seeded_home):
    conn = store.connect(seeded_home)
    conn.execute("UPDATE decisions SET payload = '{' WHERE id = 1")
    conn.commit()

    for python_reader in (
        lambda: store.recent_decisions(conn, 10),
        lambda: store.aggregate_stats(conn),
        lambda: store.load_decision(conn, "d_00001"),
    ):
        with pytest.raises(json.JSONDecodeError):
            python_reader()

    for operation, args in (
        ("recent-decisions", ("10",)),
        ("aggregate-stats", ()),
        ("load", ("d_00001",)),
    ):
        with pytest.raises(subprocess.CalledProcessError):
            _run(seeded_home, operation, *args)
    conn.close()


def test_rust_feedback_is_visible_to_python_and_rejects_invalid_input(seeded_home):
    conn = store.connect(seeded_home)
    decision_id = store.recent_ids(conn, 1)[0]
    before = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    assert json.loads(_run(seeded_home, "feedback", decision_id, "4", "useful")) is True
    assert json.loads(_run(seeded_home, "feedback", "d_99999", "4", "missing")) is False
    assert json.loads(_run(seeded_home, "feedback", decision_id, "0", "invalid")) is False
    rows = conn.execute("SELECT decision_id, rating, note FROM feedback").fetchall()
    assert len(rows) == before + 1
    assert rows[-1] == (int(decision_id.removeprefix("d_")), 4, "useful")
    conn.close()
