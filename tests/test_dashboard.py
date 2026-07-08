"""M5 — read-only dashboard rendering (pure function; no sockets needed)."""

from agentrouter.dashboard import render_html

STATS = {
    "decisions": 2,
    "by_risk": {"low": 1, "high": 1},
    "by_model": {"openai/general-purpose-model": 2},
    "by_pricing_tier": {"medium": 2},
    "feedback": {"count": 1, "avg_rating": 4.0, "acceptance_rate": 1.0},
}
RECENT = [
    {
        "decision_id": "d_00001",
        "created_at": "2026-07-08T09:00:00+00:00",
        "task": "<script>alert('xss')</script> refactor",
        "model": "openai/general-purpose-model",
        "score": 0.812,
        "risk": "low",
    }
]

EMPTY_STATS = {
    "decisions": 0,
    "by_risk": {},
    "by_model": {},
    "by_pricing_tier": {},
    "feedback": {"count": 0, "avg_rating": None, "acceptance_rate": None},
}


def test_render_shows_counts_and_rows():
    page = render_html(STATS, RECENT)
    assert "2 decisions" in page
    assert "d_00001" in page
    assert "openai/general-purpose-model" in page
    assert "acceptance 1.0" in page


def test_render_escapes_task_text():
    page = render_html(STATS, RECENT)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_render_empty_state():
    page = render_html(EMPTY_STATS, [])
    assert "no decisions logged yet" in page
    assert "0 decisions" in page


def test_page_is_read_only():
    page = render_html(STATS, RECENT)
    assert "<form" not in page and "<input" not in page and "<script" not in page
