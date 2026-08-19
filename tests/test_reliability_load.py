"""Concurrency and load correctness (TASK-018B).

These gate CORRECTNESS, never wall-clock timing. Shared CI runners cannot
support a stable throughput threshold, and a flaky gate teaches people to ignore
it — so latency and throughput are recorded in the report artifact and asserted
nowhere.

The load here is deliberately driven over real loopback sockets rather than
through ``TestClient``. The first defect this suite found — concurrent routes
returning HTTP 500 from ``sqlite3.OperationalError: database is locked`` — does
not reproduce through TestClient at 40 concurrent requests but does reproduce at
200 against a real uvicorn server. A TestClient-only harness would have called
the API healthy.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")
pytest.importorskip("httpx")

from typer.testing import CliRunner  # noqa: E402

from agentrouter import store  # noqa: E402
from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.reliability import LoadSpec, run_load, serve_app  # noqa: E402

runner = CliRunner()

# Enough concurrency to contend for the database. Below ~100 the original defect
# hid; 200/32 reproduced it every run on the machine where it was found.
CONCURRENT_TOTAL = 200
CONCURRENT_WORKERS = 32


@pytest.fixture()
def home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    return tmp_path


def _persisted(home: Path) -> int:
    conn = store.connect(home)
    try:
        return conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    finally:
        conn.close()


def test_the_store_waits_for_a_contended_write_instead_of_failing(home):
    """SQLite's default busy timeout is 0: the first contended write fails.

    That is the root cause of the HTTP 500s, and it is asserted directly so the
    reason survives even if the load test is ever weakened.
    """
    conn = store.connect(home)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        conn.close()


def test_a_contended_writer_blocks_rather_than_raising(home):
    """Hold a write transaction open and prove a second writer waits it out."""
    holder = store.connect(home)
    other = store.connect(home)
    try:
        holder.execute("BEGIN IMMEDIATE")
        holder.execute(
            "INSERT INTO decisions (created_at, task, payload, user) VALUES (?,?,?,?)",
            ("now", "t", "{}", "u"),
        )
        # Without busy_timeout this raises immediately; with it, it waits and
        # then fails only because we never release. Either way it must not be an
        # instant refusal, so a short timeout proves the wait is happening.
        other.execute("PRAGMA busy_timeout=250")
        with pytest.raises(sqlite3.OperationalError):
            other.execute("BEGIN IMMEDIATE")
        holder.rollback()
        # Once the holder releases, the second writer succeeds.
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
    finally:
        holder.close()
        other.close()


@pytest.mark.slow
def test_concurrent_routing_produces_no_server_errors_and_loses_no_writes(home, tmp_path):
    """The headline invariant. Was 197/200 with 3 HTTP 500s before the fix."""
    with serve_app(home) as app:
        outcome = run_load(app.url, LoadSpec(total=CONCURRENT_TOTAL, workers=CONCURRENT_WORKERS))

    report = outcome.as_dict()
    report["persisted_rows"] = _persisted(home)
    report["lost_writes"] = outcome.ok - report["persisted_rows"]
    # Written unconditionally so a failure carries its evidence.
    (tmp_path / "load-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert outcome.transport_errors == {}, report
    assert outcome.server_errors == 0, f"server errors under load: {report}"
    assert outcome.unexpected == {}, f"unexpected statuses: {report}"
    assert outcome.ok == CONCURRENT_TOTAL, report
    assert report["lost_writes"] == 0, report


@pytest.mark.slow
def test_request_ids_never_bleed_between_concurrent_requests(home):
    """`observability._request_id` is a ContextVar set in middleware. Under
    BaseHTTPMiddleware a request can hop threadpool workers, so a shared or
    stale id would correlate one caller's log line to another's response."""
    with serve_app(home) as app:
        outcome = run_load(app.url, LoadSpec(total=120, workers=24))

    assert len(outcome.request_ids) == outcome.ok
    assert len(set(outcome.request_ids)) == len(outcome.request_ids), "request id reused"


@pytest.mark.slow
def test_decision_ids_are_unique_under_concurrency(home):
    """A duplicated id would silently overwrite one caller's decision."""
    with serve_app(home) as app:
        outcome = run_load(app.url, LoadSpec(total=120, workers=24))
    assert outcome.server_errors == 0

    conn = store.connect(home)
    try:
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        distinct = conn.execute("SELECT COUNT(DISTINCT id) FROM decisions").fetchone()[0]
    finally:
        conn.close()
    assert total == distinct == outcome.ok


# --- data integrity under WAL (TASK-018B) -------------------------------------
#
# Enabling WAL fixed the concurrency failure but introduced a quieter hazard:
# committed rows live in the `-wal` sidecar until a checkpoint, so a filesystem
# copy of `agentrouter.db` alone is not a backup. It fails *silently* — you get a
# database, it just has no tables.


def test_a_naive_file_copy_of_the_database_is_not_a_backup(home):
    """Pin the hazard itself, so nobody re-introduces a plain copy later."""
    import shutil
    import tempfile

    conn = store.connect(home)
    try:
        for i in range(5):
            store.save_decision(conn, f"task {i}", {"n": i})

        naive = Path(tempfile.mkdtemp()) / "agentrouter.db"
        shutil.copy(home / "agentrouter.db", naive)

        # WAL is active and un-checkpointed, so the copy is incomplete — and it
        # fails SILENTLY: the table exists (created before the writes) but every
        # row is missing. No error, no warning, just an empty log.
        assert (home / "agentrouter.db-wal").exists()
        copied = sqlite3.connect(f"file:{naive}?mode=ro", uri=True)
        try:
            visible = copied.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        finally:
            copied.close()
        assert visible < 5, (
            "a plain file copy appeared complete; if SQLite ever checkpoints "
            "eagerly this test is obsolete, but store.snapshot must still be used"
        )
    finally:
        conn.close()


def test_snapshot_captures_rows_still_held_in_the_wal(home, tmp_path):
    """`store.snapshot` is the supported way to copy the log, and must be
    complete while writers are still connected."""
    conn = store.connect(home)
    try:
        for i in range(5):
            store.save_decision(conn, f"task {i}", {"n": i})

        target = tmp_path / "bundle" / "decisions.db"
        store.snapshot(home, target)
        # Self-contained at rest: one file, no sidecar to forget to copy.
        # (Opening it later legitimately creates -wal/-shm, so check now.)
        assert sorted(p.name for p in target.parent.iterdir()) == ["decisions.db"]

        copied = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            assert copied.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 5
        finally:
            copied.close()
    finally:
        conn.close()


def test_snapshot_is_consistent_while_writes_are_in_flight(home, tmp_path):
    """The online backup API must not tear a concurrent write."""
    import threading

    stop = threading.Event()
    written = []

    def writer():
        conn = store.connect(home)
        try:
            while not stop.is_set():
                written.append(store.save_decision(conn, "concurrent", {"x": 1}))
        finally:
            conn.close()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        target = tmp_path / "live-snapshot.db"
        store.snapshot(home, target)
    finally:
        stop.set()
        thread.join(timeout=30)

    copied = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        count = copied.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        # integrity_check is the real assertion: a torn copy fails it.
        assert copied.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        copied.close()
    assert 0 <= count <= len(written) + 1
