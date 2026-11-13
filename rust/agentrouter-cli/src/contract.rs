//! Deterministic OpenAPI JSON canonicalization shared with `agentrouter.contract`.
//!
//! This is the first Rust contract-tooling slice. It intentionally implements
//! only canonicalization and serialization; compatibility classification and
//! safe artifact export remain owned by Python until their full contracts are
//! ported and differentially checked.

use serde_json::{Map, Value};
use std::collections::{BTreeSet, HashSet};
use std::fmt::Write as _;

const ORDER_INSENSITIVE: &[&str] = &["required", "enum", "tags"];
const MAX_EXPANDED_NODES: usize = 200_000;

/// Recursively normalize object keys and the OpenAPI arrays whose order is not
/// semantically meaningful, matching Python's `contract._canonical` behavior.
pub fn canonicalize(value: &mut Value) {
    match value {
        Value::Object(object) => {
            // serde_json's default object map is key-sorted, just like the
            // canonical Python mapping produced here.
            let mut entries = std::mem::take(object).into_iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            let mut canonical = Map::new();
            for (key, mut child) in entries {
                canonicalize(&mut child);
                if let Value::Array(items) = &mut child {
                    if ORDER_INSENSITIVE.contains(&key.as_str())
                        && items.iter().all(Value::is_string)
                    {
                        items.sort_by(|left, right| left.as_str().cmp(&right.as_str()));
                    } else if matches!(key.as_str(), "anyOf" | "oneOf" | "allOf") {
                        items.sort_by_cached_key(json_sort_key);
                    } else if key == "parameters" {
                        items.sort_by_cached_key(parameter_sort_key);
                    }
                }
                canonical.insert(key, child);
            }
            *object = canonical;
        }
        Value::Array(items) => {
            for child in items {
                canonicalize(child);
            }
        }
        _ => {}
    }
}

/// Serialize JSON with two-space indentation, sorted object keys, literal
/// Unicode, and a final newline, as Python's `contract.dumps` does.
pub fn dumps(value: &Value) -> Result<String, serde_json::Error> {
    let mut sorted = value.clone();
    sort_object_keys(&mut sorted);
    let mut text = serde_json::to_string_pretty(&sorted)?;
    text.push('\n');
    Ok(text)
}

fn sort_object_keys(value: &mut Value) {
    match value {
        Value::Object(object) => {
            let mut entries = std::mem::take(object).into_iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            let mut sorted = Map::new();
            for (key, mut child) in entries {
                sort_object_keys(&mut child);
                sorted.insert(key, child);
            }
            *object = sorted;
        }
        Value::Array(items) => {
            for item in items {
                sort_object_keys(item);
            }
        }
        _ => {}
    }
}

/// Return invalid OpenAPI references in sorted, deduplicated order, matching
/// Python's `contract.validate_refs`. Only local object-key paths are accepted;
/// missing and cyclic references are reported so callers can fail closed.
pub fn validate_refs(document: &Value) -> Result<Vec<String>, String> {
    enum Action<'a> {
        Walk(&'a Value),
        FinishReference(String),
    }

    let mut pending = vec![Action::Walk(document)];
    let mut visiting = HashSet::<String>::new();
    let mut validated = HashSet::<String>::new();
    let mut invalid = BTreeSet::<String>::new();
    let mut remaining = MAX_EXPANDED_NODES;
    let mut scheduled_nodes = 1_usize;

    while let Some(action) = pending.pop() {
        match action {
            Action::FinishReference(reference) => {
                visiting.remove(&reference);
                validated.insert(reference);
            }
            Action::Walk(node) => {
                remaining = remaining.saturating_sub(1);
                if remaining == 0 {
                    return Err(format!(
                        "contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it"
                    ));
                }

                match node {
                    Value::Array(items) => {
                        schedule_nodes(&mut scheduled_nodes, items.len())?;
                        pending.extend(items.iter().rev().map(Action::Walk));
                    }
                    Value::Object(object) => {
                        if let Some(reference) = object.get("$ref").and_then(Value::as_str) {
                            if !reference.starts_with("#/") {
                                invalid
                                    .insert(format!("{reference} (only local refs are supported)"));
                                continue;
                            }
                            if visiting.contains(reference) {
                                invalid.insert(format!("{reference} (self-referential)"));
                                continue;
                            }
                            if validated.contains(reference) {
                                continue;
                            }
                            let Some(target) = resolve_local_reference(document, reference) else {
                                invalid.insert(format!("{reference} (unresolvable)"));
                                continue;
                            };
                            schedule_nodes(&mut scheduled_nodes, 1)?;
                            visiting.insert(reference.to_owned());
                            pending.push(Action::FinishReference(reference.to_owned()));
                            pending.push(Action::Walk(target));
                        } else {
                            let mut children = object.values().collect::<Vec<_>>();
                            children.reverse();
                            schedule_nodes(&mut scheduled_nodes, children.len())?;
                            pending.extend(children.into_iter().map(Action::Walk));
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(invalid.into_iter().collect())
}

fn schedule_nodes(scheduled: &mut usize, additional: usize) -> Result<(), String> {
    let Some(total) = scheduled.checked_add(additional) else {
        return Err(node_budget_error());
    };
    // Python's walker errors when its 200,000th node is visited, so a valid
    // document can contain at most 199,999 walked nodes including the root.
    if total >= MAX_EXPANDED_NODES {
        return Err(node_budget_error());
    }
    *scheduled = total;
    Ok(())
}

fn node_budget_error() -> String {
    format!("contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it")
}

fn resolve_local_reference<'a>(document: &'a Value, reference: &str) -> Option<&'a Value> {
    let mut target = document;
    for part in reference.strip_prefix("#/")?.split('/') {
        target = target.as_object()?.get(part)?;
    }
    Some(target)
}

fn json_sort_key(value: &Value) -> String {
    // Python uses `json.dumps(value, sort_keys=True)` with ensure_ascii enabled
    // and the default comma/colon spacing. Reproduce that text so Unicode
    // branch values sort in precisely the same order on every platform.
    match value {
        Value::Null => "null".to_owned(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => python_json_string(value),
        Value::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(json_sort_key)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(object) => {
            let mut entries = object.iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(right.0));
            format!(
                "{{{}}}",
                entries
                    .into_iter()
                    .map(|(key, value)| format!(
                        "{}: {}",
                        python_json_string(key),
                        json_sort_key(value)
                    ))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
    }
}

fn python_json_string(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\u{0008}' => output.push_str("\\b"),
            '\u{000c}' => output.push_str("\\f"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            '\u{0000}'..='\u{001f}' => {
                let _ = write!(output, "\\u{:04x}", character as u32);
            }
            '\u{007f}'..='\u{ffff}' => {
                let _ = write!(output, "\\u{:04x}", character as u32);
            }
            '\u{10000}'..='\u{10ffff}' => {
                let code = character as u32 - 0x1_0000;
                let high = 0xd800 + (code >> 10);
                let low = 0xdc00 + (code & 0x3ff);
                let _ = write!(output, "\\u{high:04x}\\u{low:04x}");
            }
            _ => output.push(character),
        }
    }
    output.push('"');
    output
}

fn parameter_sort_key(value: &Value) -> (String, String) {
    let Some(object) = value.as_object() else {
        return (String::new(), String::new());
    };
    (
        python_string(object.get("in")),
        python_string(object.get("name")),
    )
}

fn python_string(value: Option<&Value>) -> String {
    match value {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => if *value { "True" } else { "False" }.to_owned(),
        Some(value) => value.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonicalizes_semantic_lists_and_preserves_other_array_order() {
        let mut value = json!({
            "z": 1,
            "tags": ["z", "a"],
            "required": ["z", "a"],
            "enum": ["z", "a"],
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "parameters": [
                {"name": "z", "in": "query"},
                {"name": "a", "in": "path"}
            ],
            "examples": ["z", "a"]
        });
        canonicalize(&mut value);
        assert_eq!(value["required"], json!(["a", "z"]));
        assert_eq!(value["enum"], json!(["a", "z"]));
        assert_eq!(value["tags"], json!(["a", "z"]));
        assert_eq!(value["anyOf"][0]["type"], "null");
        assert_eq!(value["parameters"][0]["name"], "a");
        assert_eq!(value["examples"], json!(["z", "a"]));
        assert_eq!(value.as_object().unwrap().keys().next().unwrap(), "anyOf");
    }

    #[test]
    fn schema_branch_sort_key_matches_python_ascii_escaping() {
        let mut value = json!({"anyOf": [{"const": "z"}, {"const": "é"}]});
        canonicalize(&mut value);
        assert_eq!(value["anyOf"][0]["const"], "é");
    }

    #[test]
    fn dumps_has_python_compatible_indentation_unicode_and_newline() {
        let value = json!({"name": "AgentRouter 🧭", "nested": {"value": true}});
        assert_eq!(
            dumps(&value).unwrap(),
            "{\n  \"name\": \"AgentRouter 🧭\",\n  \"nested\": {\n    \"value\": true\n  }\n}\n"
        );
    }

    #[test]
    fn dumps_sorts_keys_without_reordering_arrays() {
        let value = json!({"z": [2, 1], "a": 0});
        assert_eq!(
            dumps(&value).unwrap(),
            "{\n  \"a\": 0,\n  \"z\": [\n    2,\n    1\n  ]\n}\n"
        );
    }

    #[test]
    fn reference_validation_reports_missing_external_and_cyclic_targets() {
        let document = json!({
            "components": {"schemas": {
                "A": {"$ref": "#/components/schemas/B"},
                "B": {"$ref": "#/components/schemas/A"}
            }},
            "paths": {"/x": {"get": {
                "responses": {"200": {"schema": {"$ref": "#/components/schemas/Missing"}}},
                "parameters": [{"schema": {"$ref": "https://example.test/schema.json"}}]
            }}}
        });
        let invalid = validate_refs(&document).unwrap();
        assert_eq!(invalid.len(), 3);
        assert!(invalid.iter().any(|item| item.contains("only local refs")));
        assert!(invalid.iter().any(|item| item.contains("unresolvable")));
        assert!(invalid.iter().any(|item| item.contains("self-referential")));
        assert!(invalid.windows(2).all(|pair| pair[0] < pair[1]));
    }

    #[test]
    fn reference_validation_has_a_bounded_node_budget() {
        let document = Value::Array(vec![Value::Null; MAX_EXPANDED_NODES]);
        assert_eq!(
            validate_refs(&document).unwrap_err(),
            format!("contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it")
        );
    }
}
