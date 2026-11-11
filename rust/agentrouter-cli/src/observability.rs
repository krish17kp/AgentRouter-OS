//! Secret-safe text helpers from `agentrouter.observability`.
//!
//! This is the shared redaction layer for Rust diagnostics and structured
//! records. Logging, request context propagation, and optional OTel remain
//! outstanding parts of the module port.

use std::fmt::Display;
use std::sync::OnceLock;

use regex::{Captures, Regex};
use serde_json::Value;
use unicode_general_category::{get_general_category, GeneralCategory};

const ECHO_LIMIT: usize = 64;
const MAX_REDACT_DEPTH: usize = 6;

fn secret_pattern() -> &'static Regex {
    static SECRET_RE: OnceLock<Regex> = OnceLock::new();
    SECRET_RE.get_or_init(|| {
        Regex::new(
            r#"(?s)(-----BEGIN[ A-Z]*PRIVATE\ KEY-----.*?-----END[ A-Z]*PRIVATE\ KEY-----|sk-[A-Za-z0-9_-]{8,}|sk_(?:live|test)_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{16,}|glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|hf_[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}|A(?:KIA|SIA|ROA|IDA|NPA|NVA)[0-9A-Z]{12,}|(?:Bearer|Basic)\s+[A-Za-z0-9+/=._-]{8,}|ey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+|[a-z][a-z0-9+.\-]*://[^\s/@]+:[^\s/@]+@|(?i:api[_\-]?key|secret|passwd|password|token|credential)(?-i:)['\"\s]*[:=]['\"\s]*[^\s'\",}\]]{6,}|[A-Za-z0-9+/]{40,}={0,2})"#,
        )
        .expect("static secret redaction pattern must compile")
    })
}

fn probably_a_path(run: &str) -> bool {
    run.contains('/') && !run.chars().any(|character| character.is_ascii_digit())
}

/// Redact known credential formats, generic key/value secrets, and long opaque
/// tokens while preserving path-shaped text without digits.
pub fn redact(text: &str) -> String {
    secret_pattern()
        .replace_all(text, |captures: &Captures<'_>| {
            let matched = captures.get(0).map_or("", |value| value.as_str());
            if probably_a_path(matched) {
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
    redact_value_at(value, 0)
}

fn redact_value_at(value: &Value, depth: usize) -> Value {
    match value {
        Value::String(text) => Value::String(redact(text)),
        Value::Array(values) if depth < MAX_REDACT_DEPTH => Value::Array(
            values
                .iter()
                .map(|item| redact_value_at(item, depth + 1))
                .collect(),
        ),
        Value::Object(values) if depth < MAX_REDACT_DEPTH => Value::Object(
            values
                .iter()
                .map(|(key, item)| (key.clone(), redact_value_at(item, depth + 1)))
                .collect(),
        ),
        Value::Null | Value::Bool(_) | Value::Number(_) => value.clone(),
        _ => Value::String(redact(&value.to_string())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

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
}
