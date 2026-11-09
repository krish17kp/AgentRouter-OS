//! User route controls are hard prefilters, never post-score nudges.
use agentrouter_registry::{ModelEntry, ReleaseChannel};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Default, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct RouteControls {
    pub vendor: Vec<String>,
    pub exclude_vendor: Vec<String>,
    pub model: Option<String>,
    pub host: Vec<String>,
    pub exclude_host: Vec<String>,
    pub max_price: Option<f64>,
    pub stable_only: bool,
    pub available_only: bool,
    pub prohibit_tool: Vec<String>,
}

impl RouteControls {
    pub fn active(&self) -> bool {
        !self.vendor.is_empty()
            || !self.exclude_vendor.is_empty()
            || self.model.is_some()
            || !self.host.is_empty()
            || !self.exclude_host.is_empty()
            || self.max_price.is_some()
            || self.stable_only
            || self.available_only
            || !self.prohibit_tool.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Exclusion {
    pub model: String,
    pub reason: String,
}

fn py_list(values: &HashSet<String>) -> String {
    let mut sorted: Vec<&str> = values.iter().map(String::as_str).collect();
    sorted.sort_unstable();
    format!(
        "[{}]",
        sorted
            .iter()
            .map(|v| format!("'{v}'"))
            .collect::<Vec<_>>()
            .join(", ")
    )
}

fn equivalents(tool: &str) -> &[&str] {
    match tool {
        "web" | "web-search" => &["web", "web-search"],
        "tool-use" | "function-calling" => &["tool-use", "function-calling"],
        _ => &[],
    }
}

fn release_channel_name(channel: &ReleaseChannel) -> &'static str {
    match channel {
        ReleaseChannel::Stable => "stable",
        ReleaseChannel::Preview => "preview",
        ReleaseChannel::Experimental => "experimental",
        ReleaseChannel::Deprecated => "deprecated",
    }
}

fn reject_reason(
    model: &ModelEntry,
    controls: &RouteControls,
    available: &HashMap<String, bool>,
) -> Option<String> {
    let vendor_in: HashSet<String> = controls.vendor.iter().map(|v| v.to_lowercase()).collect();
    let vendor_out: HashSet<String> = controls
        .exclude_vendor
        .iter()
        .map(|v| v.to_lowercase())
        .collect();
    let host_in: HashSet<String> = controls.host.iter().map(|v| v.to_lowercase()).collect();
    let host_out: HashSet<String> = controls
        .exclude_host
        .iter()
        .map(|v| v.to_lowercase())
        .collect();
    let vendor = model.vendor().to_lowercase();
    if !vendor_in.is_empty() && !vendor_in.contains(&vendor) {
        return Some(format!(
            "vendor '{}' not in --vendor {}",
            model.vendor(),
            py_list(&vendor_in)
        ));
    }
    if vendor_out.contains(&vendor) {
        return Some(format!(
            "vendor '{}' excluded by --exclude-vendor",
            model.vendor()
        ));
    }
    if let Some(pin) = &controls.model {
        let pin_lower = pin.to_lowercase();
        let vendor_key = format!("{}/{}", model.vendor(), model.model_id).to_lowercase();
        if pin_lower != vendor_key
            && pin_lower != model.key().to_lowercase()
            && pin_lower != model.model_id.to_lowercase()
        {
            return Some(format!("does not match --model {pin}"));
        }
    }
    let target_hosts: HashSet<String> = model
        .execution_targets
        .iter()
        .map(|t| t.host.to_lowercase())
        .collect();
    if !host_in.is_empty() && target_hosts.is_disjoint(&host_in) {
        return Some(format!(
            "no execution target on --host {}",
            py_list(&host_in)
        ));
    }
    if !host_out.is_empty() && !target_hosts.is_disjoint(&host_out) {
        return Some("execution host excluded by --exclude-host".to_owned());
    }
    if controls.stable_only && !matches!(model.release_channel, ReleaseChannel::Stable) {
        return Some(format!(
            "release channel '{}' is not stable (--stable-only)",
            release_channel_name(&model.release_channel)
        ));
    }
    if let Some(cap) = controls.max_price {
        if let Some(price) = model.input_price_per_million {
            if price > cap {
                return Some(format!("input price ${price:?}/1M > --max-price ${cap:?}"));
            }
        } else {
            return Some(format!(
                "input price unknown; cannot verify --max-price {cap:?}"
            ));
        }
    }
    if controls.available_only && !available.get(&model.key()).copied().unwrap_or(false) {
        return Some("no available execution host (--available-only)".to_owned());
    }
    if !controls.prohibit_tool.is_empty() {
        let support: HashSet<&str> = model.tool_support.iter().map(String::as_str).collect();
        let banned: Vec<&str> = controls
            .prohibit_tool
            .iter()
            .map(String::as_str)
            .filter(|tool| {
                support.contains(tool)
                    || equivalents(tool)
                        .iter()
                        .any(|alias| support.contains(alias))
            })
            .collect();
        if !banned.is_empty() {
            return Some(format!("supports prohibited tool(s): {}", banned.join(",")));
        }
    }
    None
}

/// Missing availability is treated as unavailable, so `available_only` fails closed.
pub fn apply_controls<'a>(
    models: &'a [ModelEntry],
    controls: &RouteControls,
    available: &HashMap<String, bool>,
) -> (Vec<&'a ModelEntry>, Vec<Exclusion>) {
    if !controls.active() {
        return (models.iter().collect(), vec![]);
    }
    let mut kept = Vec::new();
    let mut dropped = Vec::new();
    for model in models {
        if let Some(reason) = reject_reason(model, controls, available) {
            dropped.push(Exclusion {
                model: model.key(),
                reason: format!("control: {reason}"),
            });
        } else {
            kept.push(model);
        }
    }
    (kept, dropped)
}
