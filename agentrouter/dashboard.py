"""M5 — read-only local dashboard over the decision log (stdlib http.server).

Strictly read-only by construction: the handler implements GET only, and the
page has no forms or scripts. No new dependencies; recomputes from SQLite on
every request so it is always live.
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import store

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>AgentRouter OS — dashboard</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
 h1 {{ font-size: 1.3rem; }} h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ text-align: left; padding: .3rem .6rem; border-bottom: 1px solid #ddd;
           font-size: .85rem; }}
 .muted {{ color: #777; }}
</style></head><body>
<h1>AgentRouter OS — decision log (read-only)</h1>
<p class="muted">{decisions} decisions · feedback: {fb_count} ratings, avg {fb_avg},
acceptance {fb_acc}</p>
<h2>Risk distribution</h2>{risk_table}
<h2>Recommended pricing-tier distribution</h2>{tier_table}
<h2>Decisions by user</h2>{user_table}
<h2>Recent decisions</h2>{recent_table}
</body></html>"""


def _kv_table(d: dict) -> str:
    if not d:
        return '<p class="muted">none yet</p>'
    rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>" for k, v in sorted(d.items())
    )
    return f"<table><tr><th></th><th>count</th></tr>{rows}</table>"


def render_html(stats: dict, recent: list[dict]) -> str:
    """Pure HTML rendering — everything user-supplied is escaped."""
    fb = stats["feedback"]
    if recent:
        rows = "".join(
            f"<tr><td>{html.escape(r['decision_id'])}</td>"
            f"<td>{html.escape(str(r['created_at'])[:19])}</td>"
            f"<td>{html.escape(str(r.get('user', 'unknown')))}</td>"
            f"<td>{html.escape(r['task'][:80])}</td>"
            f"<td>{html.escape(r['model'])}</td>"
            f"<td>{r['score'] if r['score'] is not None else '-'}</td>"
            f"<td>{html.escape(str(r['risk']))}</td></tr>"
            for r in recent
        )
        recent_table = (
            "<table><tr><th>id</th><th>when (UTC)</th><th>user</th><th>task</th>"
            f"<th>recommended</th><th>score</th><th>risk</th></tr>{rows}</table>"
        )
    else:
        recent_table = '<p class="muted">no decisions logged yet</p>'
    return _PAGE.format(
        decisions=stats["decisions"],
        fb_count=fb["count"],
        fb_avg=fb["avg_rating"] if fb["avg_rating"] is not None else "-",
        fb_acc=fb["acceptance_rate"] if fb["acceptance_rate"] is not None else "-",
        risk_table=_kv_table(stats["by_risk"]),
        tier_table=_kv_table(stats["by_pricing_tier"]),
        user_table=_kv_table(stats.get("by_user", {})),
        recent_table=recent_table,
    )


def serve(home: Path, port: int, tier_by_key: dict[str, str]) -> None:
    """Blocking server loop. GET-only handler = no write path into routing."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            conn = store.connect(home)
            body = render_html(
                store.aggregate_stats(conn, tier_by_key), store.recent_decisions(conn)
            ).encode("utf-8")
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # quiet by default
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Dashboard: http://127.0.0.1:{httpd.server_address[1]}/ (Ctrl+C to stop)")
        httpd.serve_forever()
