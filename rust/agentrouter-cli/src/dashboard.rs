//! Read-only local decision-log dashboard, ported from `agentrouter.dashboard`.
//!
//! The HTTP listener binds only to loopback and exposes a single read-only GET
//! page. Values from tasks, users, and model names are HTML escaped.

use std::collections::HashMap;
use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::thread;

use serde_json::Value;

const PAGE: &str =
    "<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>AgentRouter OS — dashboard</title>
<style>
 body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 60rem; }
 h1 { font-size: 1.3rem; } h2 { font-size: 1rem; margin-top: 1.5rem; }
 table { border-collapse: collapse; width: 100%; }
 th, td { text-align: left; padding: .3rem .6rem; border-bottom: 1px solid #ddd;
           font-size: .85rem; }
 .muted { color: #777; }
</style></head><body>
<h1>AgentRouter OS — decision log (read-only)</h1>
<p class=\"muted\">{decisions} decisions · feedback: {fb_count} ratings, avg {fb_avg},
acceptance {fb_acc}</p>
<h2>Risk distribution</h2>{risk_table}
<h2>Recommended pricing-tier distribution</h2>{tier_table}
<h2>Decisions by user</h2>{user_table}
<h2>Recent decisions</h2>{recent_table}
</body></html>";

fn escape_html(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());
    for ch in value.chars() {
        match ch {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&#x27;"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

fn display(value: Option<&Value>, fallback: &str) -> String {
    value.map_or_else(
        || fallback.to_string(),
        |v| match v {
            Value::String(s) => s.clone(),
            _ => v.to_string(),
        },
    )
}

fn kv_table(value: Option<&Value>) -> String {
    let Some(entries) = value.and_then(Value::as_object) else {
        return "<p class=\"muted\">none yet</p>".to_string();
    };
    if entries.is_empty() {
        return "<p class=\"muted\">none yet</p>".to_string();
    }
    let rows = entries
        .iter()
        .map(|(key, count)| format!("<tr><td>{}</td><td>{}</td></tr>", escape_html(key), count))
        .collect::<String>();
    format!("<table><tr><th></th><th>count</th></tr>{rows}</table>")
}

/// Pure HTML renderer. The JSON shapes are those returned by Rust storage's
/// `aggregate_stats` and `recent_decisions` functions.
pub fn render_html(stats: &Value, recent: &[Value]) -> String {
    let feedback = stats.get("feedback");
    let recent_table = if recent.is_empty() {
        "<p class=\"muted\">no decisions logged yet</p>".to_string()
    } else {
        let rows = recent
            .iter()
            .map(|row| {
                let id = escape_html(&display(row.get("decision_id"), ""));
                let timestamp = display(row.get("created_at"), "")
                    .chars()
                    .take(19)
                    .collect::<String>();
                let created_at = escape_html(&timestamp);
                let user = escape_html(&display(row.get("user"), "unknown"));
                let task = escape_html(
                    &display(row.get("task"), "")
                        .chars()
                        .take(80)
                        .collect::<String>(),
                );
                let model = escape_html(&display(row.get("model"), ""));
                let score = row
                    .get("score")
                    .filter(|v| !v.is_null())
                    .map_or_else(|| "-".to_string(), Value::to_string);
                let risk = escape_html(&display(row.get("risk"), "null"));
                format!(
                    "<tr><td>{id}</td><td>{created_at}</td><td>{user}</td><td>{task}</td><td>{model}</td><td>{score}</td><td>{risk}</td></tr>"
                )
            })
            .collect::<String>();
        format!(
            "<table><tr><th>id</th><th>when (UTC)</th><th>user</th><th>task</th><th>recommended</th><th>score</th><th>risk</th></tr>{rows}</table>"
        )
    };
    let fb_avg = feedback
        .and_then(|v| v.get("avg_rating"))
        .filter(|v| !v.is_null())
        .map_or_else(|| "-".to_string(), Value::to_string);
    let fb_acc = feedback
        .and_then(|v| v.get("acceptance_rate"))
        .filter(|v| !v.is_null())
        .map_or_else(|| "-".to_string(), Value::to_string);
    PAGE.replace("{decisions}", &display(stats.get("decisions"), "0"))
        .replace(
            "{fb_count}",
            &display(feedback.and_then(|v| v.get("count")), "0"),
        )
        .replace("{fb_avg}", &fb_avg)
        .replace("{fb_acc}", &fb_acc)
        .replace("{risk_table}", &kv_table(stats.get("by_risk")))
        .replace("{tier_table}", &kv_table(stats.get("by_pricing_tier")))
        .replace("{user_table}", &kv_table(stats.get("by_user")))
        .replace("{recent_table}", &recent_table)
}

fn respond(mut stream: TcpStream, home: &Path, tier_by_key: &HashMap<String, String>) {
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(10)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(10)));
    let mut request = String::new();
    let _ = BufReader::new(&mut stream)
        .take(8192)
        .read_line(&mut request);
    if !request.starts_with("GET ") {
        let _ = stream.write_all(
            b"HTTP/1.1 405 Method Not Allowed\r\nAllow: GET\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        );
        return;
    }
    let result = (|| -> Result<Vec<u8>, String> {
        let conn = agentrouter_storage::connect(home).map_err(|e| e.to_string())?;
        let stats = agentrouter_storage::aggregate_stats(&conn, Some(tier_by_key))
            .map_err(|e| e.to_string())?;
        let recent = agentrouter_storage::recent_decisions(&conn, 20).map_err(|e| e.to_string())?;
        Ok(render_html(&stats, &recent).into_bytes())
    })();
    let (status, body) = match result {
        Ok(body) => ("200 OK", body),
        Err(error) => (
            "500 Internal Server Error",
            escape_html(&error).into_bytes(),
        ),
    };
    let header = format!(
        "HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(header.as_bytes());
    let _ = stream.write_all(&body);
}

/// Serve the dashboard on loopback until the process is stopped.
pub fn serve(home: &Path, port: u16, tier_by_key: &HashMap<String, String>) -> io::Result<()> {
    let listener = TcpListener::bind(("127.0.0.1", port))?;
    println!(
        "Dashboard: http://127.0.0.1:{}/ (Ctrl+C to stop)",
        listener.local_addr()?.port()
    );
    let home = PathBuf::from(home);
    for incoming in listener.incoming() {
        let stream = incoming?;
        let home = home.clone();
        let tiers = tier_by_key.clone();
        thread::spawn(move || respond(stream, &home, &tiers));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn empty_dashboard_matches_the_read_only_python_page_contract() {
        let page = render_html(
            &json!({
                "decisions": 0,
                "by_risk": {},
                "by_pricing_tier": {},
                "by_user": {},
                "feedback": {"count": 0, "avg_rating": null, "acceptance_rate": null}
            }),
            &[],
        );
        assert!(page.contains("AgentRouter OS — decision log (read-only)"));
        assert!(page.contains("0 decisions · feedback: 0 ratings, avg -,\nacceptance -"));
        assert!(page.contains("<p class=\"muted\">no decisions logged yet</p>"));
        assert!(!page.contains("<script"));
    }

    #[test]
    fn dashboard_escapes_untrusted_decision_fields() {
        let page = render_html(
            &json!({
                "decisions": 1,
                "by_risk": {"<script>alert(1)</script>": 1},
                "by_pricing_tier": {},
                "by_user": {"<user>": 1},
                "feedback": {"count": 0, "avg_rating": null, "acceptance_rate": null}
            }),
            &[json!({
                "decision_id": "d_00001",
                "created_at": "2026-11-11T00:00:00+00:00",
                "user": "<user>",
                "task": "<script>alert(1)</script>",
                "model": "<model>",
                "score": null,
                "risk": "<high>"
            })],
        );
        assert!(!page.contains("<script>"));
        assert!(page.contains("&lt;script&gt;alert(1)&lt;/script&gt;"));
        assert!(page.contains("&lt;user&gt;"));
        assert!(page.contains("&lt;model&gt;"));
    }

    #[test]
    fn dashboard_renders_recent_decision_fields_and_aggregates() {
        let page = render_html(
            &json!({
                "decisions": 2,
                "by_risk": {"high": 1, "low": 1},
                "by_pricing_tier": {"medium": 2},
                "by_user": {"krish": 2},
                "feedback": {"count": 1, "avg_rating": 4.0, "acceptance_rate": 1.0}
            }),
            &[json!({
                "decision_id": "d_00001",
                "created_at": "2026-07-08T09:00:00+00:00",
                "task": "refactor safely",
                "model": "openai/general-purpose-model",
                "score": 0.812,
                "risk": "low",
                "user": "krish"
            })],
        );
        assert!(page.contains("2 decisions"));
        assert!(page.contains("d_00001"));
        assert!(page.contains("openai/general-purpose-model"));
        assert!(page.contains("acceptance 1.0"));
        assert!(page.contains("refactor safely"));
        assert!(!page.contains("<form"));
        assert!(!page.contains("<input"));
    }
}
