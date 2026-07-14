"""Phase P3 — classification confidence & abstention."""

import json

from typer.testing import CliRunner

from agentrouter.classifier import DEFAULT_UNCERTAINTY_THRESHOLD, classify
from agentrouter.cli import app

runner = CliRunner()


def test_clear_task_is_high_confidence():
    c = classify("refactor the payment module and add unit tests")
    assert c.confidence >= 0.7
    assert not c.needs_clarification


def test_vague_task_is_low_confidence_and_flags_clarification():
    c = classify("do it")
    assert c.confidence < DEFAULT_UNCERTAINTY_THRESHOLD
    assert c.needs_clarification
    assert c.ambiguity_reason


def test_confidence_is_bounded():
    for task in ["", "x", "build a scalable distributed real-time event-driven system"]:
        c = classify(task)
        assert 0.0 <= c.confidence <= 1.0


def test_threshold_controls_clarification_flag():
    # A mid-confidence task flips needs_clarification as the threshold moves.
    c_low = classify("summarize and refactor this", uncertainty_threshold=0.0)
    c_high = classify("summarize and refactor this", uncertainty_threshold=1.0)
    assert not c_low.needs_clarification
    assert c_high.needs_clarification


def test_competing_families_surface_an_alternative():
    # "summarize" + coding verbs => two families; runner-up recorded.
    c = classify("summarize the repo and refactor the auth module")
    assert c.alternative_task_type is not None


def test_cli_json_exposes_confidence_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "do it", "--json", "--no-log"])
    assert r.exit_code == 0, r.output
    cls = json.loads(r.output)["classification"]
    assert "confidence" in cls and "needs_clarification" in cls
    assert cls["needs_clarification"] is True


def test_cli_text_shows_low_confidence_note(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["route", "do it", "--no-log"])
    assert "Low confidence" in r.output
    assert "confidence:" in r.output
