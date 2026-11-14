//! Safety-gated execution for persisted routing decisions.
//!
//! This keeps execution opt-in, revalidates the recorded safety gate against
//! the stored classification, uses argv without a shell for local tools, and
//! sends OpenAI requests only after explicit `--yes` confirmation.

use std::{path::Path, process::Command};

use agentrouter_core::Classification;
use agentrouter_registry::{load_all_models, load_providers, ModelEntry};
use serde_json::Value;

fn text<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value.get(key).and_then(Value::as_str)
}

fn fail(message: impl Into<String>) -> Result<i32, String> {
    Err(message.into())
}

fn run_argv(argv: &[String], label: &str) -> Result<i32, String> {
    let Some(program) = argv.first() else {
        return fail(format!(
            "Execution is not enabled for {label}: command is empty."
        ));
    };
    println!("Running {label}...");
    match Command::new(program).args(&argv[1..]).status() {
        Ok(status) => Ok(status.code().unwrap_or(1)),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            fail(format!("Execution failed: command not found: {program}\nNext: install or repair the configured command for {label}."))
        }
        Err(_) => fail(format!("Execution failed while starting {program}.")),
    }
}

fn current_model<'a>(models: &'a [ModelEntry], key: &str) -> Option<&'a ModelEntry> {
    models.iter().find(|model| model.key() == key)
}

fn print_host_route(
    model: &ModelEntry,
    target: &agentrouter_registry::ExecutionTarget,
    status: &agentrouter_hosts::HostStatus,
) {
    println!(
        "Model:       {} ({}/{})",
        model.name(),
        model.vendor(),
        model.model_id
    );
    println!(
        "Run through: {} (host model id {})",
        target.host, target.host_model_id
    );
    println!("Availability: {} ({})", status.availability, status.reason);
    if target.command_template.is_some() {
        println!(
            "Command:     {}",
            agentrouter_hosts::command_preview(target, true)
        );
    }
}

/// Execute a single recorded decision, returning the child process exit code
/// for command-backed providers and local CLI hosts.
pub fn run(home: &Path, args: &[String]) -> Result<i32, String> {
    if args
        .iter()
        .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
    {
        println!("Usage: agentrouter execute <decision-id> [--yes] [--dry-run]");
        return Ok(0);
    }
    let Some(decision_id) = args.first() else {
        return fail("usage: agentrouter execute <decision-id> [--yes] [--dry-run]");
    };
    let mut yes = false;
    let mut dry_run = false;
    for argument in args.iter().skip(1) {
        match argument.as_str() {
            "--yes" => yes = true,
            "--dry-run" => dry_run = true,
            option => return fail(format!("unknown execute option '{option}'")),
        }
    }

    let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
    let Some(payload) = agentrouter_storage::load_decision(&connection, decision_id)
        .map_err(|error| error.to_string())?
    else {
        eprintln!("No decision found with id '{decision_id}'.");
        let recent =
            agentrouter_storage::recent_ids(&connection, 5).map_err(|error| error.to_string())?;
        if !recent.is_empty() {
            eprintln!("Next: try a recent id: {}", recent.join(", "));
        }
        return Ok(2);
    };

    let classification: Classification = match payload.get("classification") {
        Some(value) => serde_json::from_value(value.clone()).map_err(|_| {
            "Execution blocked: stored classification is invalid; route again.".to_owned()
        })?,
        None => return fail("Execution blocked: stored classification is invalid; route again."),
    };
    let expected_gates = crate::gates_for(&classification);
    let stored_gates = payload.get("gates").unwrap_or(&Value::Null);
    if stored_gates.get("auto_execute_allowed") != expected_gates.get("auto_execute_allowed")
        || stored_gates.get("approval_level") != expected_gates.get("approval_level")
    {
        return fail("Execution blocked: stored safety gate changed; route again.");
    }
    if expected_gates["auto_execute_allowed"] != Value::Bool(true) {
        return fail(format!(
            "Execution blocked for {decision_id}.\nWhy: risk={}, approval={} - this decision requires a human to run the task themselves (NFR-8: high risk never auto-executes).\nNext: agentrouter prompt generate --from {decision_id} and run the tool yourself.",
            text(&payload["classification"], "risk").unwrap_or("unknown"),
            text(&expected_gates, "approval_level").unwrap_or("unknown")
        ));
    }

    let Some(recommendation) = payload.get("recommendation").filter(|v| !v.is_null()) else {
        return fail("Nothing to execute: this decision had no eligible model.");
    };
    let provider_id = text(recommendation, "provider").ok_or_else(|| {
        "Execution blocked: stored recommendation is invalid; route again.".to_owned()
    })?;
    let model_key = text(recommendation, "model").ok_or_else(|| {
        "Execution blocked: stored recommendation is invalid; route again.".to_owned()
    })?;
    let prompt = text(&payload, "prompt")
        .ok_or_else(|| "Execution blocked: stored prompt is invalid; route again.".to_owned())?;

    let registry = home.join("registry");
    let providers =
        load_providers(&registry.join("providers.yaml")).map_err(|error| error.to_string())?;
    let (models, warnings) =
        load_all_models(&registry, &providers).map_err(|error| error.to_string())?;
    for warning in warnings {
        eprintln!("warning: {warning}");
    }
    let provider = providers.get(provider_id);
    let legacy_opt_in =
        provider.is_some_and(|item| item.supports_execution && !item.exec_command.is_empty());

    // A dry run is an unconditional no-execution path, even when --yes was
    // also supplied. Preview only the configured argv, never the task text.
    if legacy_opt_in && dry_run {
        let provider = provider.expect("legacy opt-in checked above");
        println!(
            "Would run (provider {}): {:?}",
            provider.id, provider.exec_command
        );
        println!("Dry run: nothing executed.");
        return Ok(0);
    }
    if legacy_opt_in {
        let provider = provider.expect("legacy opt-in checked above");
        if !yes {
            println!(
                "Would run (provider {}): {:?}",
                provider.id, provider.exec_command
            );
            println!("Next: re-run with --yes to execute.");
            return Ok(2);
        }
        let argv = provider
            .exec_command
            .iter()
            .map(|argument| argument.replace("{prompt}", prompt))
            .collect::<Vec<_>>();
        return match run_argv(&argv, &format!("{model_key} via provider '{provider_id}'")) {
            Ok(code) => Ok(code),
            Err(error) => {
                eprintln!("{error}");
                Ok(3)
            }
        };
    }

    let Some(model) = current_model(&models, model_key) else {
        return fail(format!("Model '{model_key}' is no longer in the registry."));
    };
    let resolved = agentrouter_hosts::resolve_execution_route(model, true);
    let (Some(target), Some(status)) = (resolved.target, resolved.status) else {
        return fail(format!("No execution target for {model_key}."));
    };
    let recorded_route = payload.get("execution_route").unwrap_or(&Value::Null);
    if !recorded_route.is_null()
        && (text(recorded_route, "host") != Some(target.host.as_str())
            || text(recorded_route, "host_model_id") != Some(target.host_model_id.as_str())
            || text(recorded_route, "model_id") != Some(model.model_id.as_str())
            || text(recorded_route, "vendor") != Some(model.vendor()))
    {
        return fail("Execution target changed since this decision was recorded; route again.");
    }
    print_host_route(model, target, &status);
    if dry_run {
        println!("Dry run: nothing executed.");
        return Ok(0);
    }

    if target.host == "openai-api" {
        if model.vendor() != "openai" || model.provider != "openai" {
            return fail("OpenAI API target is not attached to an OpenAI model.");
        }
        let Some(provider) = provider else {
            return fail("OpenAI API execution is disabled for this provider.");
        };
        if !provider.supports_execution {
            return fail("OpenAI API execution is disabled for this provider.\nSet supports_execution: true for openai in providers.yaml to opt in.");
        }
        if !classification.tool_needs.is_empty() {
            return fail("OpenAI API text execution requires a task with no external tools.");
        }
        if status.availability != agentrouter_hosts::AVAILABLE {
            return fail(format!(
                "Not enabled: host '{}' is {} ({}).",
                target.host, status.state, status.reason
            ));
        }
        if !yes {
            println!("Next: re-run with --yes to submit this prompt to OpenAI.");
            return Ok(2);
        }
        let api_key = std::env::var("OPENAI_API_KEY")
            .ok()
            .filter(|key| !key.trim().is_empty())
            .ok_or_else(|| "OpenAI API key is no longer available; route again.".to_owned())?;
        println!("Running {} via OpenAI API...", model.name());
        let transport =
            crate::openai::HttpsOpenAITransport::new().map_err(|error| error.to_string())?;
        let result = match crate::openai::run_text_response(
            &transport,
            &target.host_model_id,
            prompt,
            &api_key,
            model
                .max_output_tokens
                .as_u64()
                .unwrap_or(u64::MAX)
                .min(u64::from(crate::openai::MAX_OUTPUT_TOKENS)) as u32,
        ) {
            Ok(result) => result,
            Err(error) => {
                eprintln!("Execution failed: {error}");
                return Ok(3);
            }
        };
        println!(
            "{}",
            result
                .chars()
                .map(|character| {
                    if character.is_control() && character != '\n' && character != '\t' {
                        '?'
                    } else {
                        character
                    }
                })
                .collect::<String>()
        );
        return Ok(0);
    }

    let Some(template) = &target.command_template else {
        println!(
            "'{}' is a {:?} host with no local command; use the vendor API/SDK with the generated prompt.",
            target.host,
            target.execution_mode
        );
        return Ok(0);
    };
    if status.availability != agentrouter_hosts::AVAILABLE {
        return fail(format!(
            "Not enabled: host '{}' is {} ({}).\nNext: install/authenticate the host, or run the generated prompt yourself.",
            target.host, status.state, status.reason
        ));
    }
    if !yes {
        println!("Next: re-run with --yes to execute (or --dry-run to preview).");
        return Ok(2);
    }
    let argv = template
        .iter()
        .map(|argument| argument.replace("{prompt}", prompt))
        .collect::<Vec<_>>();
    match run_argv(&argv, &format!("{} via {}", model.name(), target.host)) {
        Ok(code) => Ok(code),
        Err(error) => {
            eprintln!("{error}");
            Ok(3)
        }
    }
}
