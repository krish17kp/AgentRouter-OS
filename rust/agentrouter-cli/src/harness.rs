//! Evidence-based port of `agentrouter/harness.py`.
//!
//! This reports the current process environment only. It never guesses a
//! named harness from unrelated editor or host signals.

use std::collections::HashMap;

pub const CLAUDE_CODE: &str = "claude-code";
pub const CI_GITHUB_ACTIONS: &str = "ci-github-actions";
pub const CI_GENERIC: &str = "ci-generic";
pub const GENERIC: &str = "generic";
pub const UNKNOWN: &str = "unknown";

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct HarnessInfo {
    pub name: String,
    pub evidence: String,
}

/// Detect a harness from an explicit environment map. This variant makes
/// precedence and conservative fallback behavior straightforward to test.
pub fn detect_harness_from(env: &HashMap<String, String>) -> HarnessInfo {
    let result = |name: &str, evidence: &str| HarnessInfo {
        name: name.to_owned(),
        evidence: evidence.to_owned(),
    };
    if env.get("CLAUDECODE").is_some_and(|value| !value.is_empty()) {
        return result(CLAUDE_CODE, "CLAUDECODE env var is set");
    }
    if env.get("GITHUB_ACTIONS").map(String::as_str) == Some("true") {
        return result(CI_GITHUB_ACTIONS, "GITHUB_ACTIONS=true");
    }
    if env.get("CI").map(String::as_str) == Some("true") {
        return result(CI_GENERIC, "CI=true");
    }
    if env.get("TERM").is_some_and(|value| !value.is_empty())
        || env.get("SHELL").is_some_and(|value| !value.is_empty())
    {
        return result(GENERIC, "interactive shell evidence, no known-tool marker");
    }
    result(UNKNOWN, "no harness evidence found")
}

/// Detect from this process's environment. Never raises or performs I/O.
pub fn detect_harness() -> HarnessInfo {
    let env = std::env::vars_os()
        .filter_map(|(key, value)| {
            let key = key.into_string().ok()?;
            let value = value
                .into_string()
                .unwrap_or_else(|_| "\u{fffd}".to_owned());
            Some((key, value))
        })
        .collect();
    detect_harness_from(&env)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn env(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        pairs
            .iter()
            .map(|(key, value)| ((*key).to_owned(), (*value).to_owned()))
            .collect()
    }

    #[test]
    fn honors_python_precedence_and_conservative_fallbacks() {
        let cases = [
            (
                env(&[("CLAUDECODE", "1")]),
                CLAUDE_CODE,
                "CLAUDECODE env var is set",
            ),
            (
                env(&[("GITHUB_ACTIONS", "true"), ("CI", "true")]),
                CI_GITHUB_ACTIONS,
                "GITHUB_ACTIONS=true",
            ),
            (env(&[("CI", "true")]), CI_GENERIC, "CI=true"),
            (
                env(&[
                    ("GITHUB_ACTIONS", "false"),
                    ("CI", "false"),
                    ("TERM", "xterm"),
                ]),
                GENERIC,
                "interactive shell evidence, no known-tool marker",
            ),
            (
                env(&[("TERM", "xterm-256color"), ("SHELL", "/bin/bash")]),
                GENERIC,
                "interactive shell evidence, no known-tool marker",
            ),
            (env(&[]), UNKNOWN, "no harness evidence found"),
            (
                env(&[("CLAUDECODE", "1"), ("CI", "true")]),
                CLAUDE_CODE,
                "CLAUDECODE env var is set",
            ),
            (
                env(&[("SOME_UNRELATED_EDITOR_VAR", "1")]),
                UNKNOWN,
                "no harness evidence found",
            ),
        ];
        for (environment, name, evidence) in cases {
            assert_eq!(
                detect_harness_from(&environment),
                HarnessInfo {
                    name: name.to_owned(),
                    evidence: evidence.to_owned(),
                }
            );
        }
    }
}
