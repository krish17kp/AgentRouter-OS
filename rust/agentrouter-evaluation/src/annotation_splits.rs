//! Deterministic annotation dataset partitioning mirrored from
//! `agentrouter.annotation.splits`.

use std::collections::BTreeMap;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::annotation_dedup::{cluster, find_leakage, normalize};

pub const DEFAULT_RATIOS: [(&str, f64); 3] = [("train", 0.6), ("dev", 0.25), ("holdout", 0.15)];

fn bucket(cluster_key: &str, ratios: &BTreeMap<String, f64>) -> Result<&'static str, String> {
    let digest = Sha256::digest(cluster_key.as_bytes());
    let remainder = digest.iter().fold(0_u32, |value, byte| {
        (value * 256 + u32::from(*byte)) % 10_000
    });
    let point = f64::from(remainder) / 10_000.0;
    let mut cumulative = 0.0;
    for (name, default_ratio) in DEFAULT_RATIOS {
        let ratio = if ratios.is_empty() {
            default_ratio
        } else {
            *ratios
                .get(name)
                .ok_or_else(|| format!("missing split ratio '{name}'"))?
        };
        cumulative += ratio;
        if point < cumulative {
            return Ok(name);
        }
    }
    Ok("holdout")
}

fn python_repr(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut result = String::from(quote);
    for character in value.chars() {
        match character {
            '\\' => result.push_str("\\\\"),
            '\n' => result.push_str("\\n"),
            '\r' => result.push_str("\\r"),
            '\t' => result.push_str("\\t"),
            c if c == quote => {
                result.push('\\');
                result.push(c);
            }
            c if c.is_control() => result.push_str(&format!("\\x{:02x}", c as u32)),
            c => result.push(c),
        }
    }
    result.push(quote);
    result
}

fn python_float(value: f64) -> String {
    let text = value.to_string();
    if value.fract() == 0.0 {
        format!("{value:.1}")
    } else {
        text
    }
}

pub fn partition(
    items: &[Value],
    frozen_holdout_prompts: &[String],
    ratios: Option<&BTreeMap<String, f64>>,
) -> Result<Value, String> {
    let ratio_map = ratios.cloned().unwrap_or_default();
    let prompts: Vec<String> = items
        .iter()
        .enumerate()
        .map(|(index, item)| {
            item.get("prompt")
                .and_then(Value::as_str)
                .map(str::to_owned)
                .ok_or_else(|| format!("item {index} is missing a string prompt"))
        })
        .collect::<Result<_, _>>()?;
    let groups = cluster(&prompts, crate::annotation_dedup::NEAR_THRESHOLD);
    let mut assigned: BTreeMap<&str, Vec<Value>> = [
        ("train", Vec::new()),
        ("dev", Vec::new()),
        ("holdout", Vec::new()),
    ]
    .into_iter()
    .collect();

    for group in groups {
        let key = group
            .iter()
            .map(|index| normalize(&prompts[*index]))
            .min()
            .unwrap_or_default();
        let split = bucket(&key, &ratio_map)?;
        for index in group {
            let mut item = items[index].clone();
            item["split"] = json!(split);
            assigned.get_mut(split).expect("known split").push(item);
        }
    }

    if !frozen_holdout_prompts.is_empty() {
        for split in ["dev", "holdout"] {
            let candidate: Vec<String> = assigned[split]
                .iter()
                .filter_map(|item| item.get("prompt").and_then(Value::as_str))
                .map(str::to_owned)
                .collect();
            let leaks = find_leakage(
                &candidate,
                frozen_holdout_prompts,
                crate::annotation_dedup::NEAR_THRESHOLD,
            );
            if let Some(sample) = leaks.first() {
                return Err(format!(
                    "{split} split leaks against the frozen holdout: {} match {} ~ {} (score {})",
                    sample.kind,
                    python_repr(&sample.left),
                    python_repr(&sample.right),
                    python_float(sample.score),
                ));
            }
        }
    }
    for values in assigned.values_mut() {
        values.sort_by(|left, right| {
            left.get("id")
                .and_then(Value::as_str)
                .cmp(&right.get("id").and_then(Value::as_str))
        });
    }
    Ok(json!({
        "train": assigned.remove("train").unwrap_or_default(),
        "dev": assigned.remove("dev").unwrap_or_default(),
        "holdout": assigned.remove("holdout").unwrap_or_default(),
    }))
}
