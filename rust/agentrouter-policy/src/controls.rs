//! Rust port of `agentrouter/controls.py`'s `RouteControls`/`apply_controls`
//! — user overrides that narrow the candidate model pool before ranking.
//! Pure functions over the model list; the routing engine is untouched.
//! All vendor/host matching is case-insensitive. Field-for-field with the
//! Python module; see `tests/test_controls_rust_compat.py`.

use std::collections::HashSet;

use agentrouter_hosts::resolve_execution_route;
use agentrouter_registry::{ModelEntry, ReleaseChannel};

#[derive(Debug, Default, Clone)]
pub struct RouteControls {
    pub vendor: Vec<String>,
    pub exclude_vendor: Vec<String>,
    pub model: Option<String>,
    pub host: Vec<String>,
    pub exclude_host: Vec<String>,
    /// USD per 1M input tokens; `None` = no cap.
    pub max_price: Option<f64>,
    pub stable_only: bool,
    pub available_only: bool,
    /// Drop models that support any of these tools.
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Dropped {
    pub model: String,
    pub reason: String,
}

fn target_hosts(m: &ModelEntry) -> HashSet<String> {
    m.execution_targets
        .iter()
        .map(|t| t.host.to_lowercase())
        .collect()
}

/// Filters `models` by the user's route controls. Returns `(kept, dropped)`
/// where each dropped entry carries why; never mutates the input.
pub fn apply_controls(models: &[ModelEntry], c: &RouteControls) -> (Vec<ModelEntry>, Vec<Dropped>) {
    if !c.active() {
        return (models.to_vec(), vec![]);
    }

    let vendor_in: HashSet<String> = c.vendor.iter().map(|v| v.to_lowercase()).collect();
    let vendor_out: HashSet<String> = c.exclude_vendor.iter().map(|v| v.to_lowercase()).collect();
    let host_in: HashSet<String> = c.host.iter().map(|h| h.to_lowercase()).collect();
    let host_out: HashSet<String> = c.exclude_host.iter().map(|h| h.to_lowercase()).collect();
    let model_pin = c.model.as_ref().map(|m| m.to_lowercase());

    let mut kept = Vec::new();
    let mut dropped = Vec::new();
    for m in models {
        match reject_reason(
            m,
            c,
            &vendor_in,
            &vendor_out,
            &host_in,
            &host_out,
            model_pin.as_deref(),
        ) {
            Some(reason) => dropped.push(Dropped {
                model: m.key(),
                reason: format!("control: {reason}"),
            }),
            None => kept.push(m.clone()),
        }
    }
    (kept, dropped)
}

#[allow(clippy::too_many_arguments)]
fn reject_reason(
    m: &ModelEntry,
    c: &RouteControls,
    vendor_in: &HashSet<String>,
    vendor_out: &HashSet<String>,
    host_in: &HashSet<String>,
    host_out: &HashSet<String>,
    model_pin: Option<&str>,
) -> Option<String> {
    let vkey = m.vendor().to_lowercase();
    if !vendor_in.is_empty() && !vendor_in.contains(&vkey) {
        return Some(format!(
            "vendor '{}' not in --vendor {}",
            m.vendor(),
            python_sorted_list_repr(vendor_in)
        ));
    }
    if !vendor_out.is_empty() && vendor_out.contains(&vkey) {
        return Some(format!(
            "vendor '{}' excluded by --exclude-vendor",
            m.vendor()
        ));
    }
    if let Some(pin) = model_pin {
        let candidates = [
            m.vendor_key().to_lowercase(),
            m.key().to_lowercase(),
            m.model_id.to_lowercase(),
        ];
        if !candidates.contains(&pin.to_string()) {
            return Some(format!(
                "does not match --model {}",
                c.model.as_ref().unwrap()
            ));
        }
    }

    let thosts = target_hosts(m);
    if !host_in.is_empty() && thosts.is_disjoint(host_in) {
        return Some(format!(
            "no execution target on --host {}",
            python_sorted_list_repr(host_in)
        ));
    }
    if !host_out.is_empty() && !thosts.is_disjoint(host_out) {
        return Some("execution host excluded by --exclude-host".to_string());
    }

    if c.stable_only && m.release_channel != ReleaseChannel::Stable {
        return Some(format!(
            "release channel '{}' is not stable (--stable-only)",
            release_channel_value(m.release_channel)
        ));
    }

    if let Some(max_price) = c.max_price {
        match m.input_price_per_million {
            None => {
                return Some(format!(
                    "input price unknown; cannot verify --max-price {}",
                    python_float_repr(max_price)
                ))
            }
            Some(price) if price > max_price => {
                return Some(format!(
                    "input price ${}/1M > --max-price ${}",
                    python_float_repr(price),
                    python_float_repr(max_price)
                ))
            }
            Some(_) => {}
        }
    }

    if c.available_only && !resolve_execution_route(m, false).is_available() {
        return Some("no available execution host (--available-only)".to_string());
    }

    if !c.prohibit_tool.is_empty() {
        let support: HashSet<String> = m.tool_support.iter().cloned().collect();
        let banned: Vec<&str> = c
            .prohibit_tool
            .iter()
            .filter(|t| crate::taxonomy::satisfied_by(t, &support))
            .map(|s| s.as_str())
            .collect();
        if !banned.is_empty() {
            return Some(format!("supports prohibited tool(s): {}", banned.join(",")));
        }
    }

    None
}

/// Mirrors Python's `str(float)`, e.g. `1.0` rather than Rust's `1`.
fn python_float_repr(f: f64) -> String {
    if f == f.trunc() && f.is_finite() {
        format!("{f:.1}")
    } else {
        format!("{f}")
    }
}

/// Mirrors Python's `str(sorted(some_set))`, e.g. `['a', 'b']`.
fn python_sorted_list_repr(set: &HashSet<String>) -> String {
    let mut sorted: Vec<&String> = set.iter().collect();
    sorted.sort();
    let items = sorted
        .iter()
        .map(|s| format!("'{s}'"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{items}]")
}

fn release_channel_value(r: ReleaseChannel) -> &'static str {
    match r {
        ReleaseChannel::Stable => "stable",
        ReleaseChannel::Preview => "preview",
        ReleaseChannel::Experimental => "experimental",
        ReleaseChannel::Deprecated => "deprecated",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn model(yaml_extra: &str) -> ModelEntry {
        let tool_support = if yaml_extra.contains("tool_support") {
            ""
        } else {
            "tool_support: []\n"
        };
        let yaml = format!(
            "provider: p\nvendor: v\nmodel_id: m\ncontext_window: 100000\nmax_output_tokens: 8000\npricing_tier: medium\nlatency_tier: fast\nability: {{coding: 7, reasoning: 7, writing: 7}}\n{tool_support}vision_support: false\ndeprecation_status: active\n{yaml_extra}",
        );
        serde_yaml::from_str(&yaml).unwrap()
    }

    #[test]
    fn inactive_controls_keep_everything() {
        let models = vec![model("")];
        let (kept, dropped) = apply_controls(&models, &RouteControls::default());
        assert_eq!(kept.len(), 1);
        assert!(dropped.is_empty());
    }

    #[test]
    fn vendor_filter_drops_non_matching() {
        let models = vec![model("")];
        let c = RouteControls {
            vendor: vec!["other".to_string()],
            ..Default::default()
        };
        let (kept, dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
        assert_eq!(dropped.len(), 1);
        assert!(dropped[0].reason.contains("not in --vendor"));
    }

    #[test]
    fn exclude_vendor_drops_matching() {
        let models = vec![model("")];
        let c = RouteControls {
            exclude_vendor: vec!["v".to_string()],
            ..Default::default()
        };
        let (kept, _dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
    }

    #[test]
    fn stable_only_drops_non_stable_channel() {
        let models = vec![model("release_channel: preview\n")];
        let c = RouteControls {
            stable_only: true,
            ..Default::default()
        };
        let (kept, dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
        assert!(dropped[0].reason.contains("not stable"));
    }

    #[test]
    fn max_price_unknown_is_rejected_honestly() {
        let models = vec![model("")];
        let c = RouteControls {
            max_price: Some(1.0),
            ..Default::default()
        };
        let (kept, dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
        assert!(dropped[0].reason.contains("input price unknown"));
    }

    #[test]
    fn max_price_over_cap_is_rejected() {
        let models = vec![model("input_price_per_million: 5.0\n")];
        let c = RouteControls {
            max_price: Some(1.0),
            ..Default::default()
        };
        let (kept, _dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
    }

    #[test]
    fn max_price_under_cap_is_kept() {
        let models = vec![model("input_price_per_million: 0.5\n")];
        let c = RouteControls {
            max_price: Some(1.0),
            ..Default::default()
        };
        let (kept, _dropped) = apply_controls(&models, &c);
        assert_eq!(kept.len(), 1);
    }

    #[test]
    fn prohibit_tool_drops_models_supporting_it() {
        let models = vec![model("tool_support: [web-search]\n")];
        let c = RouteControls {
            prohibit_tool: vec!["web".to_string()],
            ..Default::default()
        };
        let (kept, dropped) = apply_controls(&models, &c);
        assert!(kept.is_empty());
        assert!(dropped[0].reason.contains("prohibited tool"));
    }

    #[test]
    fn model_pin_matches_model_id_case_insensitively() {
        let models = vec![model("")];
        let c = RouteControls {
            model: Some("M".to_string()),
            ..Default::default()
        };
        let (kept, _dropped) = apply_controls(&models, &c);
        assert_eq!(kept.len(), 1);
    }
}
