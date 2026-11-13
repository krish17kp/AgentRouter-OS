//! Business logic mirrored from `agentrouter.server.service`.

use std::path::Path;

use agentrouter_classifier::{classify, ClassifyOptions};
use agentrouter_core::{ApprovalLevel, Classification, Level};
use agentrouter_registry::{load_all_models, load_providers, ModelEntry};
use agentrouter_routing::{RouteResult, Weights};
use serde_json::{json, Value};

use crate::schemas::{ClassifyRequest, DryRunRequest, FeedbackRequest, RouteRequest};

fn load_registry(home: &Path) -> Result<Vec<ModelEntry>, String> {
    let registry = home.join("registry");
    let providers = load_providers(&registry.join("providers.yaml")).map_err(|e| e.to_string())?;
    let (models, _warnings) = load_all_models(&registry, &providers).map_err(|e| e.to_string())?;
    Ok(models)
}

fn classifier_options(request: &ClassifyRequest) -> Result<ClassifyOptions, String> {
    request.validate().map_err(|error| error.to_string())?;
    let context_tokens = request
        .context_tokens
        .map(|tokens| {
            u32::try_from(tokens)
                .map_err(|_| "context_tokens exceeds Rust classifier range".to_string())
        })
        .transpose()?;
    Ok(ClassifyOptions {
        context_tokens,
        risk: request.risk,
        tools: request.tools.clone(),
        uncertainty_threshold: None,
    })
}

pub fn classify_task(request: &ClassifyRequest) -> Result<Value, String> {
    let options = classifier_options(request)?;
    let result = classify(&request.task, &options);
    serde_json::to_value(result).map_err(|error| error.to_string())
}

pub fn list_models(home: &Path) -> Result<Vec<Value>, String> {
    let mut models = load_registry(home)?;
    models.sort_by(|left, right| {
        left.vendor()
            .cmp(right.vendor())
            .then_with(|| left.model_id.cmp(&right.model_id))
    });
    Ok(models
        .iter()
        .map(|model| {
            let resolved = agentrouter_hosts::resolve_execution_route(model, true);
            let availability = resolved
                .status
                .map(|status| status.availability)
                .unwrap_or_else(|| agentrouter_hosts::STATE_UNKNOWN.to_string());
            json!({
                "vendor": model.vendor(),
                "model_id": model.model_id,
                "key": model.vendor_key(),
                "release_channel": serde_json::to_value(model.release_channel).unwrap(),
                "context_window": model.context_window,
                "host_availability": availability,
            })
        })
        .collect())
}

pub fn list_hosts() -> Vec<Value> {
    agentrouter_hosts::known_hosts()
        .into_iter()
        .map(|name| {
            let status = agentrouter_hosts::detect_host(name, None);
            json!({
                "host": status.host,
                "availability": status.availability,
                "reason": status.reason,
                "state": status.state,
                "remedy": status.remedy,
            })
        })
        .collect()
}

fn safety_gates(classification: &Classification) -> Value {
    let checklist: Vec<&'static str> = match classification.risk {
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
    let auto_execute_allowed =
        classification.risk != Level::High && classification.approval_level == ApprovalLevel::Auto;
    json!({
        "checklist": checklist,
        "auto_execute_allowed": auto_execute_allowed,
        "approval_level": serde_json::to_value(classification.approval_level).unwrap(),
    })
}

fn execution_route_block(row: Option<&Value>, models: &[ModelEntry]) -> Value {
    let Some(model_key) = row.and_then(|value| value["model"].as_str()) else {
        return Value::Null;
    };
    let Some(model) = models.iter().find(|model| model.key() == model_key) else {
        return Value::Null;
    };
    if model.execution_targets.is_empty() {
        return Value::Null;
    }
    let resolved = agentrouter_hosts::resolve_execution_route(model, true);
    let target = resolved.target;
    let status = resolved.status.as_ref();
    json!({
        "vendor": model.vendor(),
        "model_id": model.model_id,
        "display_name": model.name(),
        "release_channel": serde_json::to_value(model.release_channel).unwrap(),
        "host": target.map(|value| value.host.clone()),
        "host_model_id": target.map(|value| value.host_model_id.clone()),
        "execution_mode": target.map(|value| serde_json::to_value(value.execution_mode).unwrap()),
        "availability": status.map(|value| value.availability.clone()).unwrap_or_else(|| "unknown".to_string()),
        "availability_reason": status.map(|value| value.reason.clone()).unwrap_or_else(|| "no execution target".to_string()),
        "host_state": status.map(|value| value.state.clone()).unwrap_or_else(|| agentrouter_hosts::STATE_UNKNOWN.to_string()),
        "host_remedy": status.and_then(|value| value.remedy.clone()),
        "command_preview": target.map(|value| agentrouter_hosts::command_preview(value, true)),
        "required_env": target.map(|value| value.required_env.clone()).unwrap_or_default(),
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "all_hosts": resolved.all_statuses.iter().map(|value| json!({
            "host": value.host,
            "availability": value.availability,
            "state": value.state,
        })).collect::<Vec<_>>(),
    })
}

fn execution_prompt(
    task: &str,
    target: &str,
    classification: &Classification,
    checklist: &[Value],
) -> String {
    let approval = serde_json::to_value(classification.approval_level)
        .unwrap()
        .as_str()
        .unwrap()
        .to_string();
    let risk_line = if approval == "human-approval-required" {
        "4. STOP before any irreversible action - this task requires human approval."
    } else {
        "4. Flag anything unexpected instead of guessing."
    };
    let tools = if classification.tool_needs.is_empty() {
        "none".to_string()
    } else {
        classification.tool_needs.join(", ")
    };
    let checklist_lines = checklist
        .iter()
        .map(|item| format!("- [ ] {}", item.as_str().unwrap_or_default()))
        .collect::<Vec<_>>()
        .join("\n");

    format!(
        "# Execution Prompt\n\n\
Target tool: {target}\n\n\
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
        task_type = serde_json::to_value(classification.task_type)
            .unwrap()
            .as_str()
            .unwrap(),
        complexity = serde_json::to_value(classification.complexity)
            .unwrap()
            .as_str()
            .unwrap(),
        risk = serde_json::to_value(classification.risk)
            .unwrap()
            .as_str()
            .unwrap(),
        output_type = serde_json::to_value(classification.output_type)
            .unwrap()
            .as_str()
            .unwrap(),
        context_tokens = classification.context_tokens,
        context_band = serde_json::to_value(classification.context_band)
            .unwrap()
            .as_str()
            .unwrap(),
    )
}

fn route_service_payload(
    task: &str,
    models: &[ModelEntry],
    classification: &Classification,
    prefer: Option<&str>,
) -> Result<Value, String> {
    let result: RouteResult =
        agentrouter_routing::route(models, classification, Weights::default(), prefer);
    let result_json = serde_json::to_value(result).map_err(|error| error.to_string())?;
    let recommendation = &result_json["recommendation"];
    let target = recommendation
        .get("model")
        .and_then(Value::as_str)
        .or_else(|| result_json["manual_suggestion"].as_str())
        .unwrap_or("manual/human-operator");
    let gates = safety_gates(classification);
    let checklist = gates["checklist"].as_array().cloned().unwrap_or_default();
    let prompt = execution_prompt(task, target, classification, &checklist);
    let exec_route = execution_route_block(Some(recommendation), models);
    let fallback_route = execution_route_block(Some(&result_json["fallback"]), models);

    let mut payload = json!({"classification": classification});
    let object = payload
        .as_object_mut()
        .ok_or_else(|| "route payload must be a JSON object".to_string())?;
    let result_object = result_json
        .as_object()
        .ok_or_else(|| "routing engine returned a non-object result".to_string())?;
    for (key, value) in result_object {
        object.insert(key.clone(), value.clone());
    }
    object.insert("gates".to_string(), gates);
    object.insert("prompt".to_string(), Value::String(prompt));
    object.insert("execution_route".to_string(), exec_route);
    object.insert("fallback_execution_route".to_string(), fallback_route);
    Ok(payload)
}

pub fn route_task(home: &Path, request: &RouteRequest) -> Result<Value, String> {
    request.validate().map_err(|error| error.to_string())?;
    let models = load_registry(home)?;
    let options = classifier_options(&request.classify)?;
    let classification = classify(&request.classify.task, &options);
    let payload = route_service_payload(
        &request.classify.task,
        &models,
        &classification,
        request.prefer.as_deref(),
    )?;
    let decision_id = if request.no_log {
        None
    } else {
        let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
        Some(
            agentrouter_storage::save_decision(&connection, &request.classify.task, &payload)
                .map_err(|error| error.to_string())?,
        )
    };
    let mut response = payload;
    let object = response
        .as_object_mut()
        .ok_or_else(|| "route pipeline returned a non-object payload".to_string())?;
    object.insert(
        "task".to_string(),
        Value::String(request.classify.task.clone()),
    );
    object.insert(
        "decision_id".to_string(),
        decision_id.map(Value::String).unwrap_or(Value::Null),
    );
    Ok(response)
}

pub fn get_decision(home: &Path, decision_id: &str) -> Result<Option<Value>, String> {
    let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
    agentrouter_storage::load_decision(&connection, decision_id).map_err(|error| error.to_string())
}

pub fn save_feedback(home: &Path, request: &FeedbackRequest) -> Result<bool, String> {
    request.validate().map_err(|error| error.to_string())?;
    let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
    agentrouter_storage::record_feedback_with_note(
        &connection,
        &request.decision_id,
        request.rating,
        request.note.as_deref(),
    )
    .map_err(|error| error.to_string())
}

pub fn execute_dry_run(home: &Path, request: &DryRunRequest) -> Result<Option<Value>, String> {
    request.validate().map_err(|error| error.to_string())?;
    let Some(payload) = get_decision(home, &request.decision_id)? else {
        return Ok(None);
    };
    let recommendation = payload
        .get("recommendation")
        .cloned()
        .unwrap_or(Value::Null);
    let auto_execute_allowed = payload["gates"]["auto_execute_allowed"]
        .as_bool()
        .unwrap_or(false);
    let execution_route = payload
        .get("execution_route")
        .cloned()
        .unwrap_or(Value::Null);
    let models = load_registry(home)?;
    let argv = recommendation
        .get("model")
        .and_then(Value::as_str)
        .and_then(|key| models.iter().find(|model| model.key() == key))
        .and_then(|model| agentrouter_hosts::resolve_execution_route(model, true).target)
        .and_then(|target| target.command_template.clone())
        .map(|command| json!(command))
        .unwrap_or(Value::Null);
    Ok(Some(json!({
        "decision_id": request.decision_id,
        "would_execute": false,
        "auto_execute_allowed": auto_execute_allowed,
        "recommendation": recommendation,
        "execution_route": execution_route,
        "argv": argv,
        "note": "dry-run only: no process was or will be spawned by this endpoint",
    })))
}
