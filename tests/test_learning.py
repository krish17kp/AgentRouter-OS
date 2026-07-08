"""M4 — bounded, reversible weight adaptation from stored feedback."""

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from agentrouter.engine import BASE_WEIGHTS
from agentrouter.learning import MAX_SHIFT, MIN_FEEDBACK, learned_weights

runner = CliRunner()


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE feedback (id INTEGER PRIMARY KEY, decision_id INTEGER,"
        " created_at TEXT, rating INTEGER, note TEXT)"
    )
    yield c
    c.close()


def _add_ratings(conn, ratings):
    conn.executemany(
        "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (1, 'now', ?, '')",
        [(r,) for r in ratings],
    )


# --- unit: bounds and reversibility ------------------------------------------------


def test_below_min_sample_no_adaptation(conn):
    _add_ratings(conn, [1] * (MIN_FEEDBACK - 1))
    w, note = learned_weights(conn, BASE_WEIGHTS)
    assert w == BASE_WEIGHTS and note is None


def test_positive_feedback_no_adaptation(conn):
    _add_ratings(conn, [5, 4, 5, 4])
    w, note = learned_weights(conn, BASE_WEIGHTS)
    assert w == BASE_WEIGHTS and note is None


def test_negative_feedback_shifts_within_step(conn):
    _add_ratings(conn, [1, 2, 5])  # 3 total (min sample), 2 negative
    w, note = learned_weights(conn, BASE_WEIGHTS)
    assert w["w_cap"] == pytest.approx(BASE_WEIGHTS["w_cap"] + 0.02)
    assert w["w_cost"] == pytest.approx(BASE_WEIGHTS["w_cost"] - 0.02)
    assert "2 negative" in note and "revert" in note


def test_shift_is_capped(conn):
    _add_ratings(conn, [1] * 50)  # 50 negatives would be 0.50 unbounded
    w, _ = learned_weights(conn, BASE_WEIGHTS)
    shift = w["w_cap"] - BASE_WEIGHTS["w_cap"]
    assert shift == pytest.approx(MAX_SHIFT)
    assert w["w_cost"] >= 0.05


def test_deleting_feedback_reverts(conn):
    _add_ratings(conn, [1, 1, 1])
    w, note = learned_weights(conn, BASE_WEIGHTS)
    assert note is not None and w != BASE_WEIGHTS
    conn.execute("DELETE FROM feedback")
    w2, note2 = learned_weights(conn, BASE_WEIGHTS)
    assert w2 == BASE_WEIGHTS and note2 is None


def test_weights_still_sum_to_one(conn):
    _add_ratings(conn, [1, 1, 1, 1, 1])
    w, _ = learned_weights(conn, BASE_WEIGHTS)
    assert sum(w.values()) == pytest.approx(sum(BASE_WEIGHTS.values()))


# --- end to end through the CLI -----------------------------------------------------


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


# medium complexity + low risk -> no complexity/risk weight shift, so the payload
# weights expose the (learned) base directly
def _route_json(task="refactor the logging module"):
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", task, "--json"])
    assert r.exit_code == 0, r.output
    return json.loads(r.output)


def test_feedback_changes_later_recommendation_weights(home):
    from agentrouter.cli import app

    first = _route_json()
    assert first["weights"]["w_cap"] == BASE_WEIGHTS["w_cap"]
    did = first["decision_id"]
    for _ in range(MIN_FEEDBACK):
        r = runner.invoke(app, ["feedback", did, "--rating", "1"])
        assert r.exit_code == 0, r.output

    second = _route_json()
    assert second["weights"]["w_cap"] > BASE_WEIGHTS["w_cap"]
    assert any("learned from" in s for s in second["weight_shifts"])  # change is logged


def test_learning_false_disables_adaptation(home):
    from agentrouter.cli import app

    did = _route_json()["decision_id"]
    for _ in range(MIN_FEEDBACK):
        runner.invoke(app, ["feedback", did, "--rating", "1"])
    cfg = home / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\nlearning: false\n", encoding="utf-8")

    result = _route_json()
    assert result["weights"]["w_cap"] == BASE_WEIGHTS["w_cap"]
    assert not any("learned from" in s for s in result["weight_shifts"])
