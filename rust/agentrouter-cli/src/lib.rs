//! Rust port of the `agentrouter route --json` pipeline: the parts of
//! `agentrouter/cli.py`'s `route()` command not already covered by another
//! crate, namely `safety.gates_for`, `prompts.generate_prompt`,
//! `learning.learned_weights`, `cli._apply_policy`/`_reason_for`, plus the
//! orchestration that assembles the final JSON payload. Registries,
//! classification, routing, controls, and host resolution are all delegated
//! to their own already-ported crates. See `tests/test_cli_route_rust_compat.py`.
//!
//! Scope note: this covers `route --json` with no config.yaml overrides and
//! no `--verify-live` (that flag is a documented no-op in Python today since
//! no live usage adapter is registered — see `agentrouter-usage`). `init`,
//! `explain`, `feedback`, `registry list`, `prompt generate`, `plugin`, and
//! `providers *` are not ported in this slice.

use std::collections::HashMap;
use std::path::Path;

use agentrouter_core::{ApprovalLevel, Classification, Level};
use agentrouter_registry::ModelEntry;
use agentrouter_routing::RouteResult;
use serde_json::{json, Value};

/// Mirrors `safety._CHECKLISTS` + `safety.gates_for`.
pub fn gates_for(cls: &Classification) -> Value {
    let checklist: Vec<&'static str> = match cls.risk {
        Level::Low => vec!["Sanity-check the output before using it"],
        Level::Medium => vec![
            "Review the output before acting on it",
            "Run relevant tests / verify behavior",
            "Confirm the change stays within intended scope",
        ],
        Level::High => vec![
            "Review full diff before applying",
            "Run the test suite",
            "Secret scan changed files",
            "Confirm rollback path",
            "Human sign-off (no auto-execute)",
        ],
    };
    let auto_execute_allowed = cls.risk != Level::High && cls.approval_level == ApprovalLevel::Auto;
    json!({
        "checklist": checklist,
        "auto_execute_allowed": auto_execute_allowed,
        "approval_level": serde_json::to_value(cls.approval_level).unwrap(),
    })
}

/// Mirrors `prompts.generate_prompt`.
pub fn generate_prompt(
    task: &str,
    tool_key: &str,
    cls: &Classification,
    checklist: &[Value],
) -> String {
    let approval: String = serde_json::to_value(cls.approval_level)
        .unwrap()
        .as_str()
        .unwrap()
        .to_string();
    let risk_line = if approval == "human-approval-required" {
        "4. STOP before any irreversible action - this task requires human approval."
    } else {
        "4. Flag anything unexpected instead of guessing."
    };
    let tools = if cls.tool_needs.is_empty() {
        "none".to_string()
    } else {
        cls.tool_needs.join(", ")
    };
    let checklist_lines = checklist
        .iter()
        .map(|c| format!("- [ ] {}", c.as_str().unwrap_or_default()))
        .collect::<Vec<_>>()
        .join("\n");

    format!(
        "# Execution Prompt\n\n\
Target tool: {tool_key}\n\n\
## Task\n{task}\n\n\
## Context for the executing tool\n\
- Task type: {task_type} | Complexity: {complexity} | Risk: {risk}\n\
- Expected output: {output_type}\n\
- Estimated context: ~{context_tokens} tokens ({context_band})\n\
- Tools you may need: {tools}\n\n\
## Instructions\n\
1. Restate the task in your own words before starting.\n\
2. Produce the expected output type ({output_type}).\n\
3. Keep changes minimal and within the stated scope.\n\
{risk_line}\n\n\
## Safety checklist (complete before applying results)\n\
{checklist_lines}\n",
        task_type = serde_json::to_value(cls.task_type)
            .unwrap()
            .as_str()
            .unwrap(),
        complexity = serde_json::to_value(cls.complexity)
            .unwrap()
            .as_str()
            .unwrap(),
        risk = serde_json::to_value(cls.risk).unwrap().as_str().unwrap(),
        output_type = serde_json::to_value(cls.output_type)
            .unwrap()
            .as_str()
            .unwrap(),
        context_tokens = cls.context_tokens,
        context_band = serde_json::to_value(cls.context_band)
            .unwrap()
            .as_str()
            .unwrap(),
    )
}

const MIN_FEEDBACK: i64 = 3;
const STEP: f64 = 0.01;
const MAX_SHIFT: f64 = 0.10;
const MIN_W_COST: f64 = 0.05;
const NEGATIVE_AT_OR_BELOW: i64 = 2;

/// Mirrors `learning.learned_weights`.
pub fn learned_weights(
    conn: &rusqlite::Connection,
    base: &agentrouter_routing::Weights,
) -> rusqlite::Result<(agentrouter_routing::Weights, Option<String>)> {
    let (total, negative): (i64, i64) = conn.query_row(
        "SELECT COUNT(*), COALESCE(SUM(rating <= ?1), 0) FROM feedback WHERE rating IS NOT NULL",
        rusqlite::params![NEGATIVE_AT_OR_BELOW],
        |r| Ok((r.get(0)?, r.get(1)?)),
    )?;
    if total < MIN_FEEDBACK || negative == 0 {
        return Ok((*base, None));
    }
    let shift = (STEP * negative as f64)
        .min(MAX_SHIFT)
        .min(base.w_cost - MIN_W_COST);
    if shift <= 0.0 {
        return Ok((*base, None));
    }
    let w = agentrouter_routing::Weights {
        w_cap: (base.w_cap + shift * 10000.0).round() / 10000.0,
        w_cost: (base.w_cost - shift * 10000.0).round() / 10000.0,
        ..*base
    };
    let note = format!(
        "learned from {total} rating(s), {negative} negative -> w_cap +{shift:.2}, w_cost -{shift:.2} (delete feedback or set learning: false to revert)"
    );
    Ok((w, Some(note)))
}

/// Mirrors `cli._apply_policy`'s pricing-tier cap. Returns `Err` with the
/// same message Python would print on an invalid `policy.max_pricing_tier`.
pub fn apply_policy(
    models: Vec<ModelEntry>,
    max_tier: Option<&str>,
) -> Result<Vec<ModelEntry>, String> {
    let Some(max_tier) = max_tier else {
        return Ok(models);
    };
    let tiers = ["free", "low", "medium", "high", "frontier"];
    let Some(cap) = tiers.iter().position(|t| *t == max_tier) else {
        return Err(format!(
            "Config error: policy.max_pricing_tier '{max_tier}' is not one of {tiers:?}."
        ));
    };
    Ok(models
        .into_iter()
        .filter(|m| {
            let tier_str = serde_json::to_value(m.pricing_tier).unwrap();
            let idx = tiers
                .iter()
                .position(|t| *t == tier_str.as_str().unwrap())
                .unwrap();
            idx <= cap
        })
        .collect())
}

/// Mirrors `cli._reason_for`.
pub fn reason_for(rec: &Value, cls: &Classification, shifts: &[String]) -> String {
    let t = &rec["terms"];
    let task_type = serde_json::to_value(cls.task_type)
        .unwrap()
        .as_str()
        .unwrap()
        .to_string();
    let mut parts = vec![format!(
        "strongest weighted fit for {task_type} (capability {}, cost-fit {}, context-fit {})",
        t["cap"], t["cost"], t["ctx"]
    )];
    if t["adj"].as_f64().unwrap_or(0.0) > 0.0 {
        parts.push("ideal-use-case match".to_string());
    }
    if !cls.tool_needs.is_empty() {
        parts.push(format!(
            "supports required tools: {}",
            cls.tool_needs.join(", ")
        ));
    }
    for s in shifts {
        if s.contains("quota exhausted") {
            parts.push("previous top pick skipped: quota exhausted (live-verified)".to_string());
        } else if s.contains("high") {
            parts.push("capability weighted up (high complexity/risk)".to_string());
        } else if s.contains("low") {
            parts.push("cost weighted up (simple task)".to_string());
        } else if s.contains("large") {
            parts.push("context fit weighted up (large input)".to_string());
        }
    }
    parts.join("; ")
}

/// Mirrors `hosts.execution_route_block`.
pub fn execution_route_block(
    row: Option<&Value>,
    models_by_key: &HashMap<String, &ModelEntry>,
) -> Value {
    let Some(row) = row else {
        return Value::Null;
    };
    let Some(model_key) = row["model"].as_str() else {
        return Value::Null;
    };
    let Some(model) = models_by_key.get(model_key) else {
        return Value::Null;
    };
    if model.execution_targets.is_empty() {
        return Value::Null;
    }
    let resolved = agentrouter_hosts::resolve_execution_route(model, true);
    let tgt = resolved.target;
    let status = resolved.status.as_ref();
    json!({
        "vendor": model.vendor(),
        "model_id": model.model_id,
        "display_name": model.name(),
        "release_channel": serde_json::to_value(model.release_channel).unwrap(),
        "host": tgt.map(|t| t.host.clone()),
        "host_model_id": tgt.map(|t| t.host_model_id.clone()),
        "execution_mode": tgt.map(|t| serde_json::to_value(t.execution_mode).unwrap()),
        "availability": status.map(|s| s.availability.clone()).unwrap_or_else(|| "unknown".to_string()),
        "availability_reason": status.map(|s| s.reason.clone()).unwrap_or_else(|| "no execution target".to_string()),
        "host_state": status.map(|s| s.state.clone()).unwrap_or_else(|| agentrouter_hosts::STATE_UNKNOWN.to_string()),
        "host_remedy": status.and_then(|s| s.remedy.clone()),
        "command_preview": tgt.map(|t| agentrouter_hosts::command_preview(t, true)),
        "required_env": tgt.map(|t| t.required_env.clone()).unwrap_or_default(),
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "all_hosts": resolved.all_statuses.iter().map(|s| json!({
            "host": s.host,
            "availability": s.availability,
            "state": s.state,
        })).collect::<Vec<_>>(),
    })
}

/// Full `route --json` orchestration: classify, filter/score, assemble the
/// same payload shape `cli.route()` builds (minus `decision_id`, added by
/// the caller after optionally persisting it).
pub fn route_payload(
    task: &str,
    models: &[ModelEntry],
    cls: &Classification,
    base_weights: agentrouter_routing::Weights,
    prefer: Option<&str>,
    weight_shift_note: Option<String>,
) -> Value {
    let result: RouteResult = agentrouter_routing::route(models, cls, base_weights, prefer);
    let mut result_json = serde_json::to_value(&result).unwrap();
    if let Some(note) = weight_shift_note {
        result_json["weight_shifts"]
            .as_array_mut()
            .unwrap()
            .push(Value::String(note));
    }

    let models_by_key: HashMap<String, &ModelEntry> = models.iter().map(|m| (m.key(), m)).collect();
    let rec = &result_json["recommendation"];
    let target = if !rec.is_null() {
        rec["model"].as_str().unwrap().to_string()
    } else {
        result_json["manual_suggestion"]
            .as_str()
            .map(str::to_string)
            .unwrap_or_else(|| "manual/human-operator".to_string())
    };
    let gates = gates_for(cls);
    let checklist = gates["checklist"].as_array().unwrap();
    let prompt = generate_prompt(task, &target, cls, checklist);
    let reason = if !rec.is_null() {
        let shifts: Vec<String> = result_json["weight_shifts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect();
        Value::String(reason_for(rec, cls, &shifts))
    } else {
        Value::Null
    };
    let exec_route = if !rec.is_null() {
        execution_route_block(Some(rec), &models_by_key)
    } else {
        Value::Null
    };
    let fb_route = if !result_json["fallback"].is_null() {
        execution_route_block(Some(&result_json["fallback"]), &models_by_key)
    } else {
        Value::Null
    };

    let mut payload = json!({
        "classification": serde_json::to_value(cls).unwrap(),
    });
    for (k, v) in result_json.as_object().unwrap() {
        payload[k] = v.clone();
    }
    payload["reason"] = reason;
    payload["gates"] = gates;
    payload["prompt"] = Value::String(prompt);
    payload["execution_route"] = exec_route;
    payload["fallback_execution_route"] = fb_route;
    payload
}

/// `_home()`: `AGENTROUTER_HOME` env var, else `~/.agentrouter`.
pub fn home_dir() -> std::path::PathBuf {
    std::env::var("AGENTROUTER_HOME")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| dirs_home().join(".agentrouter"))
}

fn dirs_home() -> std::path::PathBuf {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| Path::new(".").to_path_buf())
}

#[cfg(test)]
mod tests {
    use super::*;
    use agentrouter_core::{ContextBand, OutputType, TaskType};

    fn cls(risk: Level, approval: ApprovalLevel) -> Classification {
        Classification {
            task_type: TaskType::Coding,
            complexity: Level::Medium,
            risk,
            context_tokens: 2000,
            context_band: ContextBand::Small,
            output_type: OutputType::Code,
            tool_needs: vec![],
            approval_level: approval,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        }
    }

    #[test]
    fn gates_high_risk_never_auto_executes() {
        let g = gates_for(&cls(Level::High, ApprovalLevel::Auto));
        assert_eq!(g["auto_execute_allowed"], false);
        assert_eq!(g["checklist"].as_array().unwrap().len(), 5);
    }

    #[test]
    fn gates_low_risk_auto_allows_execution() {
        let g = gates_for(&cls(Level::Low, ApprovalLevel::Auto));
        assert_eq!(g["auto_execute_allowed"], true);
        assert_eq!(g["checklist"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn prompt_includes_stop_line_when_approval_required() {
        let c = cls(Level::High, ApprovalLevel::HumanApprovalRequired);
        let checklist = gates_for(&c)["checklist"].clone();
        let p = generate_prompt(
            "do it",
            "anthropic/claude",
            &c,
            checklist.as_array().unwrap(),
        );
        assert!(p.contains("STOP before any irreversible action"));
    }

    #[test]
    fn apply_policy_caps_pricing_tier() {
        use agentrouter_registry::ModelEntry;
        let make = |tier: &str| -> ModelEntry {
            let yaml = format!(
                "provider: p\nmodel_id: m\ncontext_window: 1000\nmax_output_tokens: 100\npricing_tier: {tier}\nlatency_tier: fast\nability: {{coding: 5, reasoning: 5, writing: 5}}\ntool_support: []\nvision_support: false\ndeprecation_status: active\n"
            );
            serde_yaml::from_str(&yaml).unwrap()
        };
        let models = vec![make("free"), make("frontier")];
        let kept = apply_policy(models, Some("low")).unwrap();
        assert_eq!(kept.len(), 1);
    }

    #[test]
    fn apply_policy_rejects_unknown_tier() {
        let err = apply_policy(vec![], Some("made-up")).unwrap_err();
        assert!(err.contains("Config error"));
    }

    #[test]
    fn apply_policy_none_is_identity() {
        let kept = apply_policy(vec![], None).unwrap();
        assert!(kept.is_empty());
    }
}
