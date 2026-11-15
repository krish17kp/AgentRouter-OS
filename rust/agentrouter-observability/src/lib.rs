//! Secret-safe route observability helpers from `agentrouter.observability`.
//!
//! This crate is shared by the Rust API service and CLI so route records are
//! built and redacted consistently at the logging boundary.

use std::fmt::Display;
use std::sync::OnceLock;

use regex::{Captures, Regex};
use serde_json::Value;
use sha2::{Digest, Sha256};
use unicode_general_category::{get_general_category, GeneralCategory};

const ECHO_LIMIT: usize = 64;
const MAX_REDACT_DEPTH: usize = 6;

fn secret_pattern() -> &'static Regex {
    static SECRET_RE: OnceLock<Regex> = OnceLock::new();
    SECRET_RE.get_or_init(|| {
        Regex::new(
            r#"(?s)(-----BEGIN[ A-Z]*PRIVATE\ KEY-----.*?-----END[ A-Z]*PRIVATE\ KEY-----|sk-[A-Za-z0-9_-]{8,}|sk_(?:live|test)_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{16,}|glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|hf_[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}|A(?:KIA|SIA|ROA|IDA|NPA|NVA)[0-9A-Z]{12,}|(?:Bearer|Basic)\s+[A-Za-z0-9+/=._-]{8,}|ey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+|[a-z][a-z0-9+.\-]*://[^\s/@]+:[^\s/@]+@|(?i:api[_\-]?key|secret|passwd|password|token|credential)(?-i:)['\"\s]*[:=]['\"\s]*[^\s'\",}\]]{6,}|(?P<opaque>[A-Za-z0-9+/]{40,}={0,2}))"#,
        )
        .expect("static secret redaction pattern must compile")
    })
}

fn probably_a_path(captures: &Captures<'_>, text: &str) -> bool {
    if captures.name("opaque").is_none() {
        return false;
    }
    let Some(matched) = captures.get(0) else {
        return false;
    };
    let run = matched.as_str();
    if run.matches('/').count() < 2 || run.chars().any(|character| character.is_ascii_digit()) {
        return false;
    }
    let tail: String = text[matched.end()..]
        .chars()
        .take_while(|character| {
            character.is_ascii_alphanumeric() || matches!(*character, '_' | '-' | '.')
        })
        .collect();
    matches!(
        tail.rsplit_once('.').map(|(_, extension)| extension),
        Some(
            "py" | "rs"
                | "yaml"
                | "yml"
                | "json"
                | "toml"
                | "txt"
                | "md"
                | "ts"
                | "tsx"
                | "js"
                | "html"
                | "css"
                | "sh"
        )
    )
}

/// Redact known credential formats, generic key/value secrets, and long opaque
/// tokens while preserving path-shaped text without digits.
pub fn redact(text: &str) -> String {
    redact_with_paths(text, true)
}

/// Redact opaque tokens even when they resemble diagnostic paths.
pub fn redact_strict(text: &str) -> String {
    redact_with_paths(text, false)
}

fn redact_with_paths(text: &str, preserve_paths: bool) -> String {
    secret_pattern()
        .replace_all(text, |captures: &Captures<'_>| {
            let matched = captures.get(0).map_or("", |value| value.as_str());
            if preserve_paths && probably_a_path(captures, text) {
                matched.to_string()
            } else {
                "[redacted]".to_string()
            }
        })
        .into_owned()
}

/// Remove control, format, bidi, zero-width, and line-separator characters
/// before returning user-controlled text in a human-readable error.
pub fn safe_echo(value: impl Display, limit: usize) -> String {
    let value = value.to_string();
    let cleaned: String = value
        .chars()
        .filter(|character| {
            !matches!(
                get_general_category(*character),
                GeneralCategory::Control | GeneralCategory::Format
            ) && !matches!(*character, '\u{2028}' | '\u{2029}')
        })
        .collect();
    let mut chars = cleaned.chars();
    let prefix: String = chars.by_ref().take(limit).collect();
    if chars.next().is_some() {
        format!("{prefix}…")
    } else {
        prefix
    }
}

/// Apply the standard 64-character human-readable echo limit.
pub fn safe_echo_default(value: impl Display) -> String {
    safe_echo(value, ECHO_LIMIT)
}

/// Recursively redact JSON strings and containers. Beyond the nesting bound,
/// stringify and redact the value as a fail-closed fallback.
pub fn redact_value(value: &Value) -> Value {
    redact_value_at(value, 0, true)
}

/// Redact all opaque secret shapes in structured log fields, including values
/// that happen to resemble source paths.
pub fn redact_value_strict(value: &Value) -> Value {
    redact_value_at(value, 0, false)
}

/// Stable correlation token for caller-controlled request identifiers.
pub fn log_request_id(request_id: &str) -> String {
    let digest = Sha256::digest(request_id.as_bytes());
    format!("sha256:{digest:x}")
}

/// Redact structured fields and replace raw request identifiers with a digest.
pub fn redact_log_record(record: &Value) -> Value {
    let mut safe = redact_value_strict(record);
    if let (Some(request_id), Some(fields)) = (
        record.get("request_id").and_then(Value::as_str),
        safe.as_object_mut(),
    ) {
        fields.insert(
            "request_id".to_owned(),
            Value::String(log_request_id(request_id)),
        );
    }
    safe
}

/// Build the metadata-only route record produced by Python observability.
///
/// The task text and generated prompt are deliberately excluded. The HTTP
/// service passes its request identifier explicitly so concurrent async
/// requests do not rely on thread-local state.
pub fn route_decision_record(
    task: &str,
    payload: &Value,
    decision_id: Option<&str>,
    request_id: Option<&str>,
) -> Value {
    let mut record = serde_json::Map::new();
    record.insert(
        "event".to_owned(),
        Value::String("route_decision".to_owned()),
    );
    insert_string(&mut record, "request_id", request_id);
    insert_string(&mut record, "decision_id", decision_id);

    let classification = payload
        .get("classification")
        .filter(|value| !value.is_null());
    let recommendation = payload
        .get("recommendation")
        .filter(|value| !value.is_null());
    let gates = payload.get("gates").filter(|value| !value.is_null());
    for (field, source, key) in [
        ("task_type", classification, "task_type"),
        ("risk", classification, "risk"),
        ("confidence", classification, "confidence"),
        ("recommended_model", recommendation, "model"),
        ("provider", recommendation, "provider"),
        ("pricing_tier", recommendation, "pricing_tier"),
        ("score", recommendation, "score"),
        ("auto_execute_allowed", gates, "auto_execute_allowed"),
    ] {
        if let Some(value) = source
            .and_then(|source| source.get(key))
            .filter(|value| !value.is_null())
        {
            record.insert(field.to_owned(), value.clone());
        }
    }

    let excluded = payload.get("excluded").filter(|value| json_truthy(value));
    let excluded_count = match excluded {
        Some(Value::Array(items)) => items.len(),
        Some(Value::Object(fields)) => fields.len(),
        Some(Value::String(text)) => text.chars().count(),
        _ => 0,
    };
    record.insert("excluded_count".to_owned(), Value::from(excluded_count));
    record.insert("task_len".to_owned(), Value::from(task.chars().count()));
    Value::Object(record)
}

/// Whether INFO route records were explicitly enabled by the host process.
pub fn logging_enabled() -> bool {
    std::env::var("AGENTROUTER_LOG").ok().is_some_and(|value| {
        matches!(
            value.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        )
    })
}

/// Write one redacted JSON route record when logging is enabled.
pub fn emit_route_decision(record: &Value) {
    if logging_enabled() {
        eprintln!("{}", redact_log_record(record));
    }
}

fn insert_string(record: &mut serde_json::Map<String, Value>, key: &str, value: Option<&str>) {
    if let Some(value) = value {
        record.insert(key.to_owned(), Value::String(value.to_owned()));
    }
}

fn json_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|number| number != 0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

fn sensitive_field(key: &str) -> bool {
    let normalized: String = key
        .to_lowercase()
        .chars()
        .filter(char::is_ascii_alphanumeric)
        .collect();
    [
        "apikey",
        "secret",
        "passwd",
        "password",
        "token",
        "credential",
        "authorization",
    ]
    .iter()
    .any(|marker| normalized.contains(marker))
}

fn redact_value_at(value: &Value, depth: usize, preserve_paths: bool) -> Value {
    match value {
        Value::String(text) => Value::String(redact_with_paths(text, preserve_paths)),
        Value::Array(values) if depth < MAX_REDACT_DEPTH => Value::Array(
            values
                .iter()
                .map(|item| redact_value_at(item, depth + 1, preserve_paths))
                .collect(),
        ),
        Value::Object(values) if depth < MAX_REDACT_DEPTH => Value::Object(
            values
                .iter()
                .map(|(key, item)| {
                    (
                        if preserve_paths {
                            key.clone()
                        } else {
                            redact_with_paths(key, false)
                        },
                        if !preserve_paths
                            && sensitive_field(key)
                            && !matches!(
                                item.as_str(),
                                Some("unset" | "set but blank" | "set (value withheld)")
                            )
                        {
                            Value::String("[redacted]".into())
                        } else {
                            redact_value_at(item, depth + 1, preserve_paths)
                        },
                    )
                })
                .collect(),
        ),
        Value::Null | Value::Bool(_) | Value::Number(_) => value.clone(),
        _ if !preserve_paths => Value::String("[redacted]".into()),
        _ => Value::String(redact_with_paths(&value.to_string(), preserve_paths)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn strict_structures_hide_sensitive_values_beyond_depth_limit() {
        let mut value = serde_json::json!({"api_key": "abc"});
        for _ in 0..6 {
            value = serde_json::json!({"nested": value});
        }
        let masked = redact_value_strict(&value);
        assert!(!masked.to_string().contains("abc"));
        assert!(masked.to_string().contains("[redacted]"));
        assert_eq!(
            redact_value_strict(&serde_json::json!({"APİ_KEY": "abc"})),
            serde_json::json!({"APİ_KEY": "[redacted]"})
        );
        assert_eq!(
            redact_value_at(&Value::Bool(true), 6, false),
            Value::Bool(true)
        );
    }

    #[test]
    fn redacts_provider_tokens_and_generic_secret_shapes() {
        for secret in [
            &format!("{}{}", "sk-livekey0123", "456789abcdef"),
            "sk_live_51H8xYzAbCdEfGhIj",
            "github_pat_11ABCDEFG0aBcDeFgHiJkLmN",
            "ghp_0123456789abcdefghijklmnop",
            "glpat-ABCDEFghijkl1234567890",
            "xoxb-1234567890-abcdefghij",
            "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P",
            &format!("{}{}", "AKIAIOSFODNN", "7EXAMPLE"),
            "ASIAIOSFODNN7EXAMPLE",
            "Bearer eyJhbGciOiJIUzI1NiJ9.abcdefgh.signature",
            "Basic dXNlcjpwYXNzd29yZA==",
            "postgres://user:hunter2@db.internal:5432/x",
            "postgres://user:allletters@db.internal/x",
            "provider/ABCDEFGHIJKLMNOPQRSTUVWXabcdefghijklm",
            "password=\"hunter2secret\"",
            "api_key: AbC123dEf456",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1",
        ] {
            let masked = redact(&format!("failed while using {secret} here"));
            assert!(
                !masked.contains(secret),
                "secret was not redacted: {secret}"
            );
            assert!(
                masked.contains("[redacted]"),
                "no redaction marker for {secret}"
            );
            assert!(masked.contains("failed while using"));
        }
    }

    #[test]
    fn preserves_diagnostics_and_path_shaped_strings() {
        let ordinary = "Registry file not found: providers.yaml (run: agentrouter init)";
        assert_eq!(redact(ordinary), ordinary);
        let path = "/media/krish/Projects/Agentrouteros/agentrouter/server/app.py";
        assert_eq!(redact(path), path);
    }

    #[test]
    fn redacts_nested_json_and_safe_echo_removes_line_controls() {
        let redacted = redact_value(&json!({
            "headers": {"authorization": "Bearer supersecrettoken1234"},
            "items": [1, format!("{}{}", "ghp_0123456789", "abcdefghijklmnop"), {"k": format!("{}{}", "AKIAIOSFODNN", "7EXAMPLE")}]
        }));
        let text = redacted.to_string();
        assert!(!text.contains("supersecret"));
        assert!(!text.contains("ghp_0123"));
        assert!(!text.contains("AKIAIOSF"));
        assert_eq!(safe_echo("first\nsecond\u{202e}x", 64), "firstsecondx");
        assert_eq!(safe_echo("abcdefghijklmnopqrstuvwxyz", 5), "abcde…");
    }

    #[test]
    fn structured_logs_hash_request_ids_and_redact_nested_keys() {
        let request_id = "ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklm/nopqrstuvwxyz.py";
        let record = json!({
            "event": "route_decision",
            "request_id": request_id,
            "detail": {"ghp_abcdefghijklmnopqrstuvwx": request_id},
        });
        let safe = redact_log_record(&record);
        let text = safe.to_string();
        assert!(!text.contains(request_id));
        assert!(!text.contains("ghp_"));
        assert_eq!(safe["request_id"], log_request_id(request_id));
        assert_eq!(safe["detail"]["[redacted]"], "[redacted].py");
    }

    #[test]
    fn route_record_keeps_metadata_and_omits_task_and_prompt() {
        let payload = json!({
            "classification": {"task_type": "coding", "risk": "low", "confidence": 0.9},
            "recommendation": {"model": "openai/gpt-x", "provider": "openai", "pricing_tier": "mid", "score": 1.23},
            "gates": {"auto_execute_allowed": true},
            "excluded": [{"model": "a"}, {"model": "b"}],
            "prompt": "never put prompt text in logs"
        });
        let record = route_decision_record("λx", &payload, Some("d_1"), Some("request-1"));
        assert_eq!(
            record,
            json!({
                "event": "route_decision",
                "request_id": "request-1",
                "decision_id": "d_1",
                "task_type": "coding",
                "risk": "low",
                "confidence": 0.9,
                "recommended_model": "openai/gpt-x",
                "provider": "openai",
                "pricing_tier": "mid",
                "score": 1.23,
                "auto_execute_allowed": true,
                "excluded_count": 2,
                "task_len": 2
            })
        );
        let serialized = record.to_string();
        assert!(!serialized.contains("λx"));
        assert!(!serialized.contains("prompt"));
    }
}
