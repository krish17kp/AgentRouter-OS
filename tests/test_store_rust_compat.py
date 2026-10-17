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
    python_stats = store.aggregate_stats(store.connect(seeded_home))
    rust_stats = json.loads(_run(seeded_home, "aggregate-stats"))
    assert rust_stats == python_stats


def test_load_decision_matches(seeded_home):
    [first_id] = store.recent_ids(store.connect(seeded_home), 1)
    python_decision = store.load_decision(store.connect(seeded_home), first_id)
    rust_decision = json.loads(_run(seeded_home, "load", first_id))
    assert rust_decision == python_decision


def test_load_unknown_decision_matches(seeded_home):
    python_decision = store.load_decision(store.connect(seeded_home), "d_99999")
    rust_decision = json.loads(_run(seeded_home, "load", "d_99999"))
    assert rust_decision == python_decision
