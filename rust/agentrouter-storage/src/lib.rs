//! Rust port of `agentrouter/store.py` — the SQLite DecisionLog
//! (ARCHITECTURE.md §2.11). Field-for-field with the Python module: same
//! schema, same `d_NNNNN` id format, same WAL + busy_timeout tuning, same
//! in-process write serialization. See `tests/test_store_rust_compat.py`.

use std::path::Path;
use std::sync::Mutex;

use rusqlite::{params, types::Type, Connection, OptionalExtension};
use serde_json::Value;

const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    payload TEXT NOT NULL,
    user TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL REFERENCES decisions(id),
    created_at TEXT NOT NULL,
    rating INTEGER,
    note TEXT
);
";

const BUSY_TIMEOUT_MS: u32 = 15_000;

/// The process-wide serializer for SQLite writes, mirroring Python's
/// `_WRITE_LOCK`: SQLite permits exactly one writer, so queuing in-process
/// converts "compete and sometimes fail" into "queue and always succeed".
static WRITE_LOCK: Mutex<()> = Mutex::new(());

/// M7 identity: `AGENTROUTER_USER` wins (shared-home teams), else the OS
/// user (checked the same env vars `getpass.getuser()` checks, in order,
/// skipping the pwd-database fallback since there is no Rust stdlib
/// equivalent and CI/containers always set one of these).
pub fn current_user() -> String {
    std::env::var("AGENTROUTER_USER")
        .ok()
        .filter(|v| !v.is_empty())
        .or_else(|| std::env::var("LOGNAME").ok())
        .or_else(|| std::env::var("USER").ok())
        .or_else(|| std::env::var("LNAME").ok())
        .or_else(|| std::env::var("USERNAME").ok())
        .unwrap_or_else(|| "unknown".to_string())
}

fn ensure_schema(conn: &mut Connection) -> rusqlite::Result<()> {
    let tables: Vec<String> = conn
        .prepare("SELECT name FROM sqlite_master WHERE type='table'")?
        .query_map([], |r| r.get(0))?
        .collect::<rusqlite::Result<Vec<String>>>()?;
    let ready = if tables.iter().any(|t| t == "decisions") && tables.iter().any(|t| t == "feedback")
    {
        let cols: Vec<String> = conn
            .prepare("PRAGMA table_info(decisions)")?
            .query_map([], |r| r.get(1))?
            .collect::<rusqlite::Result<Vec<String>>>()?;
        cols.iter().any(|column| column == "user")
    } else {
        false
    };
    if ready {
        return Ok(());
    }

    // DDL and the legacy M7 column migration run behind a database-wide write
    // reservation. Other processes wait, then recheck after acquiring it, so
    // two first-use connections cannot both attempt to add the same column.
    let transaction = conn.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    transaction.execute_batch(SCHEMA)?;
    let cols: Vec<String> = transaction
        .prepare("PRAGMA table_info(decisions)")?
        .query_map([], |r| r.get(1))?
        .collect::<rusqlite::Result<Vec<String>>>()?;
    if !cols.iter().any(|column| column == "user") {
        transaction.execute("ALTER TABLE decisions ADD COLUMN user TEXT", [])?;
    }
    transaction.commit()?;
    Ok(())
}

/// Opens (creating if needed) the decision log at `home/agentrouter.db`.
pub fn connect(home: &Path) -> rusqlite::Result<Connection> {
    std::fs::create_dir_all(home).map_err(|e| {
        rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(rusqlite::ffi::SQLITE_CANTOPEN),
            Some(e.to_string()),
        )
    })?;
    let mut conn = Connection::open(home.join("agentrouter.db"))?;
    // Best-effort, same as Python's contextlib.suppress(sqlite3.DatabaseError).
    let _ = conn.pragma_update(None, "journal_mode", "WAL");
    conn.pragma_update(None, "busy_timeout", BUSY_TIMEOUT_MS)?;
    ensure_schema(&mut conn)?;
    Ok(conn)
}

/// Writes a complete, self-contained copy of the decision log to
/// `destination` via SQLite's online backup API (safe under WAL; a plain
/// filesystem copy is not — see the Python module's docstring).
pub fn snapshot(home: &Path, destination: &Path) -> rusqlite::Result<()> {
    let source = connect(home)?;
    if let Some(parent) = destination.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let mut target = Connection::open(destination)?;
    let backup = rusqlite::backup::Backup::new(&source, &mut target)?;
    backup.run_to_completion(5, std::time::Duration::from_millis(250), None)?;
    Ok(())
}

fn decision_id(rowid: i64) -> String {
    format!("d_{rowid:05}")
}

fn parse_payload(payload_json: &str, column: usize) -> rusqlite::Result<Value> {
    serde_json::from_str(payload_json).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(column, Type::Text, Box::new(error))
    })
}

/// Parse the public ID argument the same way Python's `int(value)` does for
/// ordinary decimal ID strings. Python strips `d_` when present but also
/// accepts bare numbers, signs, surrounding whitespace, and digit separators.
fn parse_decision_rowid(value: &str) -> Option<i64> {
    let value = value.strip_prefix("d_").unwrap_or(value).trim();
    let bytes = value.as_bytes();
    if bytes.is_empty() {
        return None;
    }

    let mut normalized = String::with_capacity(value.len());
    let mut index = 0;
    if matches!(bytes[0], b'+' | b'-') {
        normalized.push(bytes[0] as char);
        index += 1;
    }
    let mut previous_was_digit = false;
    let mut saw_digit = false;
    while index < bytes.len() {
        match bytes[index] {
            b'0'..=b'9' => {
                normalized.push(bytes[index] as char);
                previous_was_digit = true;
                saw_digit = true;
            }
            b'_' if previous_was_digit && bytes.get(index + 1).is_some_and(u8::is_ascii_digit) => {
                previous_was_digit = false;
            }
            _ => return None,
        }
        index += 1;
    }
    if !saw_digit || !previous_was_digit {
        return None;
    }
    normalized.parse().ok()
}

pub fn save_decision(conn: &Connection, task: &str, payload: &Value) -> rusqlite::Result<String> {
    let _guard = WRITE_LOCK.lock().unwrap();
    let now = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros, true);
    conn.execute(
        "INSERT INTO decisions (created_at, task, payload, user) VALUES (?1, ?2, ?3, ?4)",
        params![
            now,
            task,
            serde_json::to_string(payload).unwrap(),
            current_user()
        ],
    )?;
    Ok(decision_id(conn.last_insert_rowid()))
}

pub fn recent_ids(conn: &Connection, n: i64) -> rusqlite::Result<Vec<String>> {
    conn.prepare("SELECT id FROM decisions ORDER BY id DESC LIMIT ?1")?
        .query_map(params![n], |r| r.get::<_, i64>(0))?
        .map(|r| r.map(decision_id))
        .collect()
}

/// Newest-first summaries for stats/dashboard (id, time, task, pick, score, risk).
pub fn recent_decisions(conn: &Connection, n: i64) -> rusqlite::Result<Vec<Value>> {
    let rows: Vec<(i64, String, String, String, Option<String>)> = conn
        .prepare(
            "SELECT id, created_at, task, payload, user FROM decisions ORDER BY id DESC LIMIT ?1",
        )?
        .query_map(params![n], |r| {
            Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;

    rows.into_iter()
        .map(|(rowid, created_at, task, payload_json, user)| {
            let p = parse_payload(&payload_json, 3)?;
            let rec = p.get("recommendation").cloned().unwrap_or(Value::Null);
            let model = rec
                .get("model")
                .and_then(Value::as_str)
                .map(str::to_string)
                .unwrap_or_else(|| "(no eligible model)".to_string());
            let risk = p
                .get("classification")
                .and_then(|c| c.get("risk"))
                .cloned()
                .unwrap_or(Value::Null);
            Ok(serde_json::json!({
                "decision_id": decision_id(rowid),
                "created_at": created_at,
                "task": task,
                "model": model,
                "score": rec.get("score").cloned().unwrap_or(Value::Null),
                "risk": risk,
                "user": user.unwrap_or_else(|| "unknown".to_string()),
            }))
        })
        .collect()
}

/// Telemetry aggregates: decision counts, risk/model/tier distributions, feedback.
pub fn aggregate_stats(
    conn: &Connection,
    tier_by_key: Option<&std::collections::HashMap<String, String>>,
) -> rusqlite::Result<Value> {
    let total: i64 = conn.query_row("SELECT COUNT(*) FROM decisions", [], |r| r.get(0))?;

    let mut by_risk: std::collections::BTreeMap<String, i64> = Default::default();
    let mut by_model: std::collections::BTreeMap<String, i64> = Default::default();
    let mut by_user: std::collections::BTreeMap<String, i64> = Default::default();
    let rows: Vec<(String, Option<String>)> = conn
        .prepare("SELECT payload, user FROM decisions")?
        .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    for (payload_json, user) in rows {
        let p = parse_payload(&payload_json, 0)?;
        let risk = p
            .get("classification")
            .and_then(|c| c.get("risk"))
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string();
        *by_risk.entry(risk).or_insert(0) += 1;
        let model = p
            .get("recommendation")
            .and_then(|r| r.get("model"))
            .and_then(Value::as_str)
            .unwrap_or("(no eligible model)")
            .to_string();
        *by_model.entry(model).or_insert(0) += 1;
        *by_user
            .entry(user.unwrap_or_else(|| "unknown".to_string()))
            .or_insert(0) += 1;
    }
    let mut by_tier: std::collections::BTreeMap<String, i64> = Default::default();
    for (model, n) in &by_model {
        let tier = tier_by_key
            .and_then(|m| m.get(model))
            .cloned()
            .unwrap_or_else(|| "unknown".to_string());
        *by_tier.entry(tier).or_insert(0) += n;
    }

    let (fb_total, fb_sum, fb_accepted): (i64, i64, i64) = conn.query_row(
        "SELECT COUNT(*), COALESCE(SUM(rating), 0), COALESCE(SUM(rating >= 4), 0) \
         FROM feedback WHERE rating IS NOT NULL",
        [],
        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
    )?;

    Ok(serde_json::json!({
        "decisions": total,
        "by_risk": by_risk,
        "by_model": by_model,
        "by_pricing_tier": by_tier,
        "by_user": by_user,
        "feedback": {
            "count": fb_total,
            "avg_rating": if fb_total > 0 {
                Some(round_ratio_hundredths(fb_sum, fb_total))
            } else {
                None
            },
            "acceptance_rate": if fb_total > 0 {
                Some(round_ratio_hundredths(fb_accepted, fb_total))
            } else {
                None
            },
        },
    }))
}

/// Round an exact integer ratio to two decimal places using Python's
/// round-half-to-even rule (`round(value, 2)`). Integer arithmetic avoids the
/// platform-dependent half-way behavior of `f64::round`.
fn round_ratio_hundredths(numerator: i64, denominator: i64) -> f64 {
    let scaled = i128::from(numerator) * 100;
    let denominator = i128::from(denominator);
    let quotient = scaled / denominator;
    let remainder = scaled % denominator;
    let twice_remainder = remainder.abs() * 2;
    let rounded = if twice_remainder > denominator.abs()
        || (twice_remainder == denominator.abs() && quotient % 2 != 0)
    {
        quotient + scaled.signum()
    } else {
        quotient
    };
    rounded as f64 / 100.0
}

pub fn load_decision(conn: &Connection, decision_id_str: &str) -> rusqlite::Result<Option<Value>> {
    let Some(rowid) = parse_decision_rowid(decision_id_str) else {
        return Ok(None);
    };
    let row: Option<(String, String, String, Option<String>)> = conn
        .query_row(
            "SELECT created_at, task, payload, user FROM decisions WHERE id = ?1",
            params![rowid],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )
        .optional()?;
    let Some((created_at, task, payload_json, user)) = row else {
        return Ok(None);
    };
    let mut payload = parse_payload(&payload_json, 2)?;
    if let Value::Object(map) = &mut payload {
        map.insert("created_at".to_string(), Value::String(created_at));
        map.insert("task".to_string(), Value::String(task));
        map.insert(
            "decision_id".to_string(),
            Value::String(decision_id_str.to_string()),
        );
        map.insert(
            "user".to_string(),
            Value::String(user.unwrap_or_else(|| "unknown".to_string())),
        );
    }
    Ok(Some(payload))
}

/// Record a 1–5 outcome rating for an existing decision. The insert checks
/// existence in one SQLite statement so a stale id cannot create orphaned
/// feedback between a separate lookup and write.
pub fn record_feedback(
    conn: &Connection,
    decision_id_str: &str,
    rating: i64,
    note: &str,
) -> rusqlite::Result<bool> {
    record_feedback_with_note(conn, decision_id_str, rating, Some(note))
}

/// Optional-note variant for the HTTP API, where omitted and empty notes have
/// distinct JSON/SQLite meaning.
pub fn record_feedback_with_note(
    conn: &Connection,
    decision_id_str: &str,
    rating: i64,
    note: Option<&str>,
) -> rusqlite::Result<bool> {
    if !(1..=5).contains(&rating) {
        return Ok(false);
    }
    let Some(rowid_str) = decision_id_str.strip_prefix("d_") else {
        return Ok(false);
    };
    let Ok(rowid) = rowid_str.parse::<i64>() else {
        return Ok(false);
    };
    let _guard = WRITE_LOCK.lock().unwrap();
    let now = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros, false);
    let inserted = conn.execute(
        "INSERT INTO feedback (decision_id, created_at, rating, note) \
         SELECT id, ?1, ?2, ?3 FROM decisions WHERE id = ?4",
        params![now, rating, note, rowid],
    )?;
    Ok(inserted == 1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn save_then_load_round_trips() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        let payload = json!({"recommendation": {"model": "m"}});
        let id = save_decision(&conn, "do thing", &payload).unwrap();
        assert_eq!(id, "d_00001");
        let loaded = load_decision(&conn, &id).unwrap().unwrap();
        assert_eq!(loaded["task"], "do thing");
        assert_eq!(loaded["decision_id"], id);
    }

    #[test]
    fn feedback_requires_existing_decision_and_valid_rating() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        let id = save_decision(&conn, "task", &json!({})).unwrap();
        assert!(!record_feedback(&conn, "d_99999", 4, "no row").unwrap());
        assert!(!record_feedback(&conn, &id, 0, "bad rating").unwrap());
        assert!(!record_feedback(&conn, &id, 6, "bad rating").unwrap());
        assert!(record_feedback(&conn, &id, 4, "worked").unwrap());
        let (rating, note): (i64, String) = conn
            .query_row("SELECT rating, note FROM feedback", [], |r| {
                Ok((r.get(0)?, r.get(1)?))
            })
            .unwrap();
        assert_eq!((rating, note.as_str()), (4, "worked"));
        assert!(record_feedback_with_note(&conn, &id, 3, None).unwrap());
        let note: Option<String> = conn
            .query_row(
                "SELECT note FROM feedback ORDER BY id DESC LIMIT 1",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(note, None);
    }

    #[test]
    fn load_unknown_id_returns_none() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        assert!(load_decision(&conn, "d_99999").unwrap().is_none());
        assert!(load_decision(&conn, "not-an-id").unwrap().is_none());
    }

    #[test]
    fn load_accepts_python_integer_id_forms() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        save_decision(&conn, "task", &json!({"value": "kept"})).unwrap();

        for supplied_id in ["1", "d_1", "+1", " 1 ", "d_0_01"] {
            let loaded = load_decision(&conn, supplied_id).unwrap().unwrap();
            assert_eq!(loaded["decision_id"], supplied_id);
            assert_eq!(loaded["value"], "kept");
        }
        for invalid_id in ["", "_1", "1_", "d__1", "1.0"] {
            assert!(load_decision(&conn, invalid_id).unwrap().is_none());
        }
    }

    #[test]
    fn malformed_persisted_json_is_an_error_for_every_payload_reader() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        conn.execute(
            "INSERT INTO decisions (created_at, task, payload, user) VALUES ('now', 'task', '{', NULL)",
            [],
        )
        .unwrap();

        assert!(recent_decisions(&conn, 10).is_err());
        assert!(aggregate_stats(&conn, None).is_err());
        assert!(load_decision(&conn, "d_00001").is_err());
    }

    #[test]
    fn recent_ids_newest_first() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        for i in 0..3 {
            save_decision(&conn, &format!("task {i}"), &json!({})).unwrap();
        }
        assert_eq!(recent_ids(&conn, 2).unwrap(), vec!["d_00003", "d_00002"]);
    }

    #[test]
    fn concurrent_connections_upgrade_legacy_schema_once() {
        use std::sync::{Arc, Barrier};
        use std::thread;

        let dir = tempfile::tempdir().unwrap();
        let legacy = Connection::open(dir.path().join("agentrouter.db")).unwrap();
        legacy
            .execute_batch(
                "CREATE TABLE decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, \
                 created_at TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL); \
                 CREATE TABLE feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, \
                 decision_id INTEGER NOT NULL, created_at TEXT NOT NULL, \
                 rating INTEGER, note TEXT);",
            )
            .unwrap();
        drop(legacy);

        let workers = 16;
        let barrier = Arc::new(Barrier::new(workers));
        let handles = (0..workers)
            .map(|_| {
                let home = dir.path().to_path_buf();
                let barrier = Arc::clone(&barrier);
                thread::spawn(move || {
                    barrier.wait();
                    let conn = connect(&home).unwrap();
                    let user_columns: i64 = conn
                        .query_row(
                            "SELECT COUNT(*) FROM pragma_table_info('decisions') WHERE name='user'",
                            [],
                            |row| row.get(0),
                        )
                        .unwrap();
                    assert_eq!(user_columns, 1);
                })
            })
            .collect::<Vec<_>>();
        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn snapshot_copies_committed_rows() {
        let dir = tempfile::tempdir().unwrap();
        let conn = connect(dir.path()).unwrap();
        save_decision(&conn, "task", &json!({})).unwrap();
        let dest = dir.path().join("backup.db");
        snapshot(dir.path(), &dest).unwrap();
        let copy = Connection::open(&dest).unwrap();
        let count: i64 = copy
            .query_row("SELECT COUNT(*) FROM decisions", [], |r| r.get(0))
            .unwrap();
        assert_eq!(count, 1);
    }
}
