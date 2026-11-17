//! Drives the ported `route --json` pipeline against a real
//! `AGENTROUTER_HOME` (registries + optional config.yaml + decision log),
//! printing the same payload shape `agentrouter route --json` prints
//! (without the `decision_id`/`task` wrapper keys added by the caller, see
//! `agentrouter_cli::route_payload`). Exists purely so
//! `tests/test_cli_route_rust_compat.py` can diff Rust output against
//! Python's `agentrouter route` CLI for the same registries and task.
//!
//! Usage: route_cli <home> <task> [prefer] [--save] [--verify-live] [route controls]
//! `--save` persists the Rust decision into the existing SQLite log and emits
//! the Python CLI's `{decision_id, task, ...payload}` JSON envelope.

use std::path::PathBuf;

use agentrouter_classifier::{classify, ClassifyOptions};
use agentrouter_core::Level;
use agentrouter_policy::controls::RouteControls;
use agentrouter_registry::{load_all_models, load_providers};

struct RouteCliOptions {
    save: bool,
    verify_live: bool,
    no_log: bool,
    prefer: Option<String>,
    controls: RouteControls,
    classify: ClassifyOptions,
}

fn parse_options(extra: Vec<String>) -> Result<RouteCliOptions, String> {
    let mut args = extra.into_iter();
    let mut save = false;
    let mut verify_live = false;
    let mut no_log = false;
    let mut prefer = None;
    let mut controls = RouteControls::default();
    let mut classify = ClassifyOptions::default();
    let mut preference_flags = Vec::new();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--save" => save = true,
            "--no-log" => no_log = true,
            "--verify-live" => verify_live = true,
            "--json" => {}
            "--context-tokens" => {
                let value = args.next().ok_or("--context-tokens needs a value")?;
                let integer = value
                    .parse::<i128>()
                    .map_err(|_| "--context-tokens must be an integer")?;
                classify.context_tokens = Some(
                    serde_json::Number::from_i128(integer)
                        .ok_or("--context-tokens is outside the supported integer range")?,
                );
            }
            "--risk" => {
                let value = args.next().ok_or("--risk needs a value")?;
                classify.risk = Some(match value.as_str() {
                    "low" => Level::Low,
                    "medium" => Level::Medium,
                    "high" => Level::High,
                    _ => return Err("--risk must be low, medium, or high".to_owned()),
                });
            }
            "--tool" => {
                let value = args.next().ok_or("--tool needs a value")?;
                classify.tools = Some(
                    value
                        .split(',')
                        .map(str::trim)
                        .filter(|tool| !tool.is_empty())
                        .map(str::to_owned)
                        .collect(),
                );
            }
            "--uncertainty-threshold" => {
                let value = args.next().ok_or("--uncertainty-threshold needs a value")?;
                classify.uncertainty_threshold = Some(
                    value
                        .parse::<f64>()
                        .map_err(|_| "--uncertainty-threshold must be numeric")?,
                );
            }
            "--vendor" => controls
                .vendor
                .push(args.next().ok_or("--vendor needs a value")?),
            "--exclude-vendor" => controls
                .exclude_vendor
                .push(args.next().ok_or("--exclude-vendor needs a value")?),
            "--model" => controls.model = Some(args.next().ok_or("--model needs a value")?),
            "--host" => controls
                .host
                .push(args.next().ok_or("--host needs a value")?),
            "--exclude-host" => controls
                .exclude_host
                .push(args.next().ok_or("--exclude-host needs a value")?),
            "--max-price" => {
                let cap: f64 = args
                    .next()
                    .ok_or("--max-price needs a value")?
                    .parse()
                    .map_err(|_| "--max-price must be numeric")?;
                if !cap.is_finite() || cap < 0.0 {
                    return Err("--max-price must be finite and non-negative".to_string());
                }
                controls.max_price = Some(cap);
            }
            "--stable-only" => controls.stable_only = true,
            "--allow-preview" => {}
            "--available-only" => controls.available_only = true,
            "--include-unavailable" => {}
            "--prohibit-tool" => {
                let tool = args.next().ok_or("--prohibit-tool needs a value")?;
                if !agentrouter_policy::taxonomy::is_known(&tool) {
                    return Err(format!("unknown prohibited tool {tool}"));
                }
                controls.prohibit_tool.push(tool);
            }
            "--prefer-quality" => preference_flags.push("quality"),
            "--prefer-balanced" => preference_flags.push("balanced"),
            "--prefer-cheap" => preference_flags.push("cheap"),
            "--prefer-fast" => preference_flags.push("fast"),
            name if name.starts_with('-') => return Err(format!("unknown option {name}")),
            name if prefer.is_none() => prefer = Some(name.to_string()),
            name => return Err(format!("unexpected argument {name}")),
        }
    }
    if preference_flags.len() > 1 {
        return Err(format!(
            "Use only one --prefer-* flag (got {})",
            preference_flags.join(", ")
        ));
    }
    if let Some(flag) = preference_flags.pop() {
        if prefer.is_some() {
            return Err("a positional preference cannot be combined with --prefer-*".to_owned());
        }
        prefer = Some(flag.to_owned());
    }
    if let Some(name) = &prefer {
        if !agentrouter_policy::preference_weights().contains_key(name.as_str()) {
            return Err(format!("unknown routing preference {name}"));
        }
    }
    if no_log {
        save = false;
    }
    Ok(RouteCliOptions {
        save,
        verify_live,
        no_log,
        prefer,
        controls,
        classify,
    })
}

fn main() {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .expect("usage: route_cli <home> <task> [prefer]"),
    );
    let task = args
        .next()
        .expect("usage: route_cli <home> <task> [prefer]");
    let options = parse_options(args.collect()).expect("valid route options");

    let reg_dir = home.join("registry");
    let providers = load_providers(&reg_dir.join("providers.yaml")).expect("load providers");
    let (models, _warnings) = load_all_models(&reg_dir, &providers).expect("load models");
    let (configured_weights, learning, max_tier) =
        agentrouter_cli::load_route_config(&home).expect("load config");
    let models = agentrouter_cli::apply_policy(models, max_tier.as_deref()).expect("apply policy");

    let cls = classify(&task, &options.classify);

    let conn = agentrouter_storage::connect(&home).expect("connect store");
    let (weights, note) = if learning {
        agentrouter_learning::learned_weights(&conn, &configured_weights).expect("learned weights")
    } else {
        (configured_weights, None)
    };

    let mut payload = agentrouter_cli::route_payload_with_controls(
        &task,
        &models,
        &cls,
        weights,
        agentrouter_cli::RouteOptions {
            prefer: options.prefer.as_deref(),
            weight_shift_note: note,
            controls: &options.controls,
            verify_live: options.verify_live,
        },
    );
    if options.save && !options.no_log {
        let decision_id = agentrouter_storage::save_decision(&conn, &task, &payload)
            .expect("save decision to existing SQLite log");
        payload["decision_id"] = serde_json::json!(decision_id);
        payload["task"] = serde_json::json!(task);
    }
    println!("{}", serde_json::to_string(&payload).unwrap());
}
