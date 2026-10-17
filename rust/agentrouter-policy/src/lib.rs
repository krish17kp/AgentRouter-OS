//! Rust port of the policy-layer pieces of `agentrouter/taxonomy.py` and
//! `agentrouter/controls.py` that don't depend on `hosts.py` (not yet
//! ported — see `RUST_MIGRATION_PLAN.md` port order). `controls.py`'s
//! `RouteControls`/`apply_controls` (the `--vendor`/`--host`/`--available-only`
//! CLI filters) are deferred until `agentrouter-hosts` exists; only the
//! preference-weight table, which is pure data, is ported here.

use std::collections::HashMap;

pub mod controls;

pub mod taxonomy {
    use std::collections::HashSet;

    /// Canonical capability labels (command.md P4). Mirrors
    /// `taxonomy.TOOLS` field-for-field.
    pub const TOOLS: &[&str] = &[
        "file-read",
        "file-edit",
        "shell",
        "code-execution",
        "browser-automation",
        "web-search",
        "network-http",
        "database-read",
        "database-write",
        "cloud-read",
        "cloud-write",
        "git-read",
        "git-write",
        "issue-tracker",
        "vision",
        "audio",
        "structured-output",
        "function-calling",
        "long-running-agent",
        "parallel-subagents",
        "web",
        "tool-use",
    ];

    const EQUIV_GROUPS: &[&[&str]] = &[&["web", "web-search"], &["tool-use", "function-calling"]];

    pub fn is_known(tool: &str) -> bool {
        TOOLS.contains(&tool)
    }

    /// True if a model/host offering `supported` covers the `required` tool.
    /// Mirrors `taxonomy.satisfied_by`: members of the same equivalence
    /// group satisfy each other; anything else must match literally.
    pub fn satisfied_by(required: &str, supported: &HashSet<String>) -> bool {
        for group in EQUIV_GROUPS {
            if group.contains(&required) {
                return group.iter().any(|g| supported.contains(*g));
            }
        }
        supported.contains(required)
    }
}

/// Preference name -> weight vector (each sums to 1.0), from
/// `controls.PREFERENCE_WEIGHTS`. A user preference is an explicit intent,
/// so it overrides the routing engine's complexity/context weight shifts.
pub fn preference_weights() -> HashMap<&'static str, HashMap<&'static str, f64>> {
    let mut m = HashMap::new();
    m.insert(
        "quality",
        HashMap::from([
            ("w_cap", 0.65),
            ("w_cost", 0.10),
            ("w_lat", 0.10),
            ("w_ctx", 0.15),
        ]),
    );
    m.insert(
        "cheap",
        HashMap::from([
            ("w_cap", 0.20),
            ("w_cost", 0.55),
            ("w_lat", 0.10),
            ("w_ctx", 0.15),
        ]),
    );
    m.insert(
        "fast",
        HashMap::from([
            ("w_cap", 0.25),
            ("w_cost", 0.15),
            ("w_lat", 0.45),
            ("w_ctx", 0.15),
        ]),
    );
    m.insert(
        "balanced",
        HashMap::from([
            ("w_cap", 0.45),
            ("w_cost", 0.25),
            ("w_lat", 0.15),
            ("w_ctx", 0.15),
        ]),
    );
    m
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn web_and_web_search_are_equivalent() {
        let supported: HashSet<String> = ["web-search".to_string()].into_iter().collect();
        assert!(taxonomy::satisfied_by("web", &supported));
    }

    #[test]
    fn unrelated_tools_are_not_satisfied() {
        let supported: HashSet<String> = ["shell".to_string()].into_iter().collect();
        assert!(!taxonomy::satisfied_by("vision", &supported));
    }

    #[test]
    fn preference_weights_each_sum_to_one() {
        for (_name, weights) in preference_weights() {
            let total: f64 = weights.values().sum();
            assert!((total - 1.0).abs() < 1e-9);
        }
    }
}
