"""Differential contract tests for Rust's feedback-weight adaptation."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess

import pytest

from agentrouter.engine import BASE_WEIGHTS
from agentrouter.learning import learned_weights

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _python_result(ratings, weights):
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE feedback (rating INTEGER)")
        conn.executemany("INSERT INTO feedback (rating) VALUES (?)", [(r,) for r in ratings])
        adapted, note = learned_weights(conn, weights)
        return {"weights": adapted, "note": note}
    finally:
        conn.close()


def _rust_result(ratings, weights):
    process = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "learning_from_json"],
        cwd="rust/agentrouter-learning",
        input=json.dumps({"ratings": ratings, "weights": weights}),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    ("ratings", "weights"),
    [
        ([], BASE_WEIGHTS),
        ([1, 2], BASE_WEIGHTS),
        ([4, 5, 5], BASE_WEIGHTS),
        ([1, 2, 5], BASE_WEIGHTS),
        ([1] * 50, BASE_WEIGHTS),
        ([None, 1, 2, 3], BASE_WEIGHTS),
        ([1, 2, 3], {**BASE_WEIGHTS, "w_cap": 0.35565, "w_cost": 0.3}),
        (
            [1, 2, 3],
            {"w_cap": 0.4, "w_cost": 0.06, "w_lat": 0.2, "w_ctx": 0.34},
        ),
        (
            [1, 2, 3],
            {"w_cap": 0.45, "w_cost": 0.05, "w_lat": 0.25, "w_ctx": 0.25},
        ),
    ],
)
def test_learned_weights_match_python(ratings, weights):
    assert _rust_result(ratings, weights) == _python_result(ratings, weights)
