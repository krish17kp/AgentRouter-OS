//! Deterministic annotation artifact storage mirrored from
//! `agentrouter.annotation.store`.

use std::collections::BTreeMap;
use std::io::Write;
use std::path::Path;

use serde::Serialize;
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

use crate::annotation_schema::{AdjudicatedItem, Candidate, DatasetManifest, ItemLabels};

fn mkdir_parent(path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    Ok(())
}

/// Match Python `Path.write_text(..., encoding="utf-8")` newline translation.
fn write_python_text(path: &Path, text: &str) -> Result<(), String> {
    let windows_text;
    let contents = if cfg!(windows) {
        windows_text = text.replace('\n', "\r\n");
        windows_text.as_str()
    } else {
        text
    };
    std::fs::write(path, contents).map_err(|error| error.to_string())
}

fn to_python_payload<T: Serialize>(value: &T) -> Result<Value, String> {
    let mut value = serde_json::to_value(value).map_err(|error| error.to_string())?;
    omit_nulls(&mut value);
    Ok(value)
}

fn to_python_yaml_payload<T: Serialize>(value: &T) -> Result<serde_yaml::Value, String> {
    json_to_yaml(to_python_payload(value)?)
}

fn json_to_yaml(value: Value) -> Result<serde_yaml::Value, String> {
    match value {
        Value::Null => Ok(serde_yaml::Value::Null),
        Value::Bool(value) => Ok(serde_yaml::Value::Bool(value)),
        Value::Number(value) => {
            let number = if let Some(value) = value.as_i64() {
                serde_yaml::Number::from(value)
            } else if let Some(value) = value.as_u64() {
                serde_yaml::Number::from(value)
            } else if value.is_f64() {
                let value = value
                    .as_f64()
                    .ok_or("annotation YAML number is outside the supported range")?;
                serde_yaml::Number::from(value)
            } else {
                return Err("annotation YAML number is outside the supported range".to_owned());
            };
            Ok(serde_yaml::Value::Number(number))
        }
        Value::String(value) => Ok(serde_yaml::Value::String(value)),
        Value::Array(values) => values
            .into_iter()
            .map(json_to_yaml)
            .collect::<Result<Vec<_>, _>>()
            .map(serde_yaml::Value::Sequence),
        Value::Object(values) => {
            let mut mapping = serde_yaml::Mapping::new();
            for (key, value) in values {
                mapping.insert(key, json_to_yaml(value)?);
            }
            Ok(serde_yaml::Value::Mapping(mapping))
        }
    }
}

fn yaml_document(schema: &str, key: &str, items: Vec<serde_yaml::Value>) -> serde_yaml::Value {
    let mut mapping = serde_yaml::Mapping::new();
    mapping.insert("schema", serde_yaml::Value::String(schema.to_owned()));
    mapping.insert(key, serde_yaml::Value::Sequence(items));
    serde_yaml::Value::Mapping(mapping)
}

fn omit_nulls(value: &mut Value) {
    match value {
        Value::Object(object) => {
            object.retain(|_, value| !value.is_null());
            for value in object.values_mut() {
                omit_nulls(value);
            }
        }
        Value::Array(values) => values.iter_mut().for_each(omit_nulls),
        _ => {}
    }
}

fn sort_keys(value: Value) -> Value {
    match value {
        Value::Object(object) => {
            let sorted = object
                .into_iter()
                .map(|(key, value)| (key, sort_keys(value)))
                .collect::<BTreeMap<_, _>>();
            let mut out = Map::new();
            for (key, value) in sorted {
                out.insert(key, value);
            }
            Value::Object(out)
        }
        Value::Array(values) => Value::Array(values.into_iter().map(sort_keys).collect()),
        other => other,
    }
}

fn python_ascii_json(value: &Value, pretty: bool) -> Result<String, String> {
    let sorted = sort_keys(value.clone());
    let json = if pretty {
        serde_json::to_string_pretty(&sorted)
    } else {
        serde_json::to_string(&sorted)
    }
    .map_err(|error| error.to_string())?;
    Ok(escape_non_ascii(&json))
}

struct PythonJsonFormatter;

impl serde_json::ser::Formatter for PythonJsonFormatter {
    fn begin_array_value<W>(&mut self, writer: &mut W, first: bool) -> std::io::Result<()>
    where
        W: ?Sized + Write,
    {
        if !first {
            writer.write_all(b", ")?;
        }
        Ok(())
    }

    fn begin_object_key<W>(&mut self, writer: &mut W, first: bool) -> std::io::Result<()>
    where
        W: ?Sized + Write,
    {
        if !first {
            writer.write_all(b", ")?;
        }
        Ok(())
    }

    fn begin_object_value<W>(&mut self, writer: &mut W) -> std::io::Result<()>
    where
        W: ?Sized + Write,
    {
        writer.write_all(b": ")
    }
}

fn python_spaced_json(value: &Value) -> Result<String, String> {
    let sorted = sort_keys(value.clone());
    let mut bytes = Vec::new();
    let mut serializer = serde_json::Serializer::with_formatter(&mut bytes, PythonJsonFormatter);
    sorted
        .serialize(&mut serializer)
        .map_err(|error| error.to_string())?;
    let json = String::from_utf8(bytes).map_err(|error| error.to_string())?;
    Ok(escape_non_ascii(&json))
}

fn escape_non_ascii(json: &str) -> String {
    let mut out = String::with_capacity(json.len());
    for character in json.chars() {
        let code = character as u32;
        if code <= 0x7f {
            out.push(character);
        } else if code <= 0xffff {
            out.push_str(&format!("\\u{code:04x}"));
        } else {
            let value = code - 0x1_0000;
            let high = 0xd800 + (value >> 10);
            let low = 0xdc00 + (value & 0x3ff);
            out.push_str(&format!("\\u{high:04x}\\u{low:04x}"));
        }
    }
    out
}

fn parse_document(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_yaml::from_str(&text).map_err(|error| error.to_string())
}

pub fn split_sha256(items: &[AdjudicatedItem]) -> Result<String, String> {
    let mut ordered = items.iter().collect::<Vec<_>>();
    ordered.sort_by(|left, right| left.id.cmp(&right.id));
    let payload = ordered
        .into_iter()
        .map(to_python_payload)
        .collect::<Result<Vec<_>, _>>()?;
    let canonical = python_ascii_json(&Value::Array(payload), false)?;
    let digest = Sha256::digest(canonical.as_bytes());
    Ok(digest.iter().map(|byte| format!("{byte:02x}")).collect())
}

pub fn save_candidates(path: &Path, candidates: &[Candidate]) -> Result<(), String> {
    mkdir_parent(path)?;
    let candidates = candidates
        .iter()
        .map(to_python_yaml_payload)
        .collect::<Result<Vec<_>, _>>()?;
    let document = yaml_document("context-band-candidates", "candidates", candidates);
    let yaml = serde_yaml::to_string(&document).map_err(|error| error.to_string())?;
    write_python_text(path, &yaml)
}

pub fn load_candidates(path: &Path) -> Result<Vec<Candidate>, String> {
    let raw = parse_document(path)?;
    let candidates = raw
        .get("candidates")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    candidates
        .into_iter()
        .map(|value| {
            let candidate: Candidate = serde_json::from_value(value).map_err(|e| e.to_string())?;
            candidate.validate()?;
            Ok(candidate)
        })
        .collect()
}

pub fn save_labels(path: &Path, items: &[ItemLabels]) -> Result<(), String> {
    mkdir_parent(path)?;
    let mut output = String::new();
    for item in items {
        let value = sort_keys(to_python_payload(item)?);
        output.push_str(&python_spaced_json(&value)?);
        output.push('\n');
    }
    write_python_text(path, &output)
}

pub fn load_labels(path: &Path) -> Result<Vec<ItemLabels>, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(|line| {
            let value: Value = serde_json::from_str(line).map_err(|error| error.to_string())?;
            let item: ItemLabels =
                serde_json::from_value(value).map_err(|error| error.to_string())?;
            item.validate()?;
            Ok(item)
        })
        .collect()
}

pub fn save_dataset(path: &Path, items: &[AdjudicatedItem]) -> Result<(), String> {
    mkdir_parent(path)?;
    let mut ordered = items.iter().collect::<Vec<_>>();
    ordered.sort_by(|left, right| left.id.cmp(&right.id));
    let items = ordered
        .into_iter()
        .map(to_python_yaml_payload)
        .collect::<Result<Vec<_>, _>>()?;
    let document = yaml_document("context-band-dataset", "items", items);
    let yaml = serde_yaml::to_string(&document).map_err(|error| error.to_string())?;
    write_python_text(path, &yaml)
}

pub fn load_dataset(path: &Path) -> Result<Vec<AdjudicatedItem>, String> {
    let raw = parse_document(path)?;
    raw.get("items")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .map(|value| {
            let item: AdjudicatedItem = serde_json::from_value(value).map_err(|e| e.to_string())?;
            item.validate()?;
            Ok(item)
        })
        .collect()
}

pub fn save_manifest(path: &Path, manifest: &DatasetManifest) -> Result<(), String> {
    mkdir_parent(path)?;
    let value = to_python_payload(manifest)?;
    let mut json = python_ascii_json(&value, true)?;
    json.push('\n');
    write_python_text(path, &json)
}

pub fn load_manifest(path: &Path) -> Result<DatasetManifest, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&text).map_err(|error| error.to_string())
}
