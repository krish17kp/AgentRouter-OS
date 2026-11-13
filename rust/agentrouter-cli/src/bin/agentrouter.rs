//! Unified Rust command entry point for the AgentRouter commands migrated so far.
//!
//! This binary dispatches to sibling compatibility executables installed by
//! the same Cargo package. The annotation workflow is linked directly from the
//! evaluation crate so it does not depend on a second package installation.

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;

use agentrouter_registry::{load_all_models, load_providers, ModelEntry};

fn usage() -> &'static str {
    "usage: agentrouter <init|route|explain|feedback|stats|prompt|registry|providers|hosts|models|doctor|server|mcp|dashboard|dataset|eval> [options]\n\nRust commands currently available:\n  init [--force]\n  route <task> [preference] [routing controls] [--json]\n  explain <decision-id>\n  feedback <decision-id> --rating 1..5 [--note TEXT]\n  stats [--json]\n  prompt generate --from <decision-id> [--tool <host>]\n  registry list [options]\n  providers <status|doctor|refresh [PROVIDER] [--limit N] [--match TEXT] [--dry-run]|rollback PROVIDER|restore PROVIDER>\n  hosts <list|doctor|show HOST>\n  models <list|show KEY>\n  doctor [options]\n  server [--host HOST] [--port PORT]\n  mcp (stdio server)\n  dashboard [port]\n  dataset <annotation workflow command>\n  eval <evaluation command> (requires agentrouter-evaluate installed)"
}

fn home() -> Result<PathBuf, String> {
    if let Some(path) = env::var_os("AGENTROUTER_HOME") {
        return Ok(PathBuf::from(path));
    }
    #[cfg(windows)]
    let user_home = env::var_os("USERPROFILE");
    #[cfg(not(windows))]
    let user_home = env::var_os("HOME");
    user_home
        .map(PathBuf::from)
        .map(|path| path.join(".agentrouter"))
        .ok_or_else(|| {
            "Set AGENTROUTER_HOME or HOME to choose the AgentRouter data directory.".to_owned()
        })
}

fn sibling_executable(name: &str) -> Result<PathBuf, String> {
    let current = env::current_exe().map_err(|error| error.to_string())?;
    let parent = current
        .parent()
        .ok_or_else(|| "cannot resolve the AgentRouter executable directory".to_owned())?;
    #[cfg(windows)]
    let name = format!("{name}.exe");
    #[cfg(not(windows))]
    let name = name.to_owned();
    let path = parent.join(name);
    if path.is_file() {
        Ok(path)
    } else {
        Err(format!(
            "Rust command '{}' is missing beside this executable. Build/install the agentrouter-cli package with all binaries.",
            path.display()
        ))
    }
}

fn run_sibling(name: &str, args: impl IntoIterator<Item = String>) -> Result<i32, String> {
    let executable = sibling_executable(name)?;
    let status = Command::new(executable)
        .args(args)
        .status()
        .map_err(|error| error.to_string())?;
    Ok(status.code().unwrap_or(1))
}

fn with_home(home: &Path, tail: impl IntoIterator<Item = String>) -> Vec<String> {
    std::iter::once(home.to_string_lossy().into_owned())
        .chain(tail)
        .collect()
}

fn load_catalog(home: &Path) -> Result<Vec<ModelEntry>, String> {
    let registry = home.join("registry");
    let providers = load_providers(&registry.join("providers.yaml"))
        .map_err(|error| format!("Registry error: {error}"))?;
    let (models, warnings) = load_all_models(&registry, &providers)
        .map_err(|error| format!("Registry error: {error}"))?;
    for warning in warnings {
        eprintln!("warning: {warning}");
    }
    Ok(models)
}

fn option_text(value: Option<&str>) -> &str {
    value.unwrap_or("None")
}

fn grouped(value: u32) -> String {
    let digits = value.to_string();
    let mut reversed = String::with_capacity(digits.len() + digits.len() / 3);
    for (index, digit) in digits.chars().rev().enumerate() {
        if index > 0 && index % 3 == 0 {
            reversed.push(',');
        }
        reversed.push(digit);
    }
    reversed.chars().rev().collect()
}

fn hosts_list(home: &Path) -> Result<i32, String> {
    let models = load_catalog(home)?;
    let mut seen = BTreeMap::new();
    for model in &models {
        for target in &model.execution_targets {
            seen.entry(target.host.clone())
                .or_insert_with(|| agentrouter_hosts::target_status(target));
        }
    }
    for host in agentrouter_hosts::known_hosts() {
        seen.entry(host.to_owned())
            .or_insert_with(|| agentrouter_hosts::detect_host(host, None));
    }
    for (host, status) in seen {
        println!("{host:<16} {:<14} {}", status.state, status.reason);
    }
    Ok(0)
}

fn hosts_doctor() -> Result<i32, String> {
    let mut ready = Vec::new();
    let mut fixable = Vec::new();
    for host in agentrouter_hosts::known_hosts() {
        let status = agentrouter_hosts::detect_host(host, None);
        let mark = if status.availability == agentrouter_hosts::AVAILABLE {
            "OK  "
        } else {
            "--  "
        };
        println!(
            "[{mark}] {:<16} {:<14} {}",
            host, status.state, status.reason
        );
        if let Some(remedy) = &status.remedy {
            println!("{:22} -> {remedy}", "");
        }
        if status.availability == agentrouter_hosts::AVAILABLE && host != "manual" {
            ready.push(host);
        } else if status.remedy.is_some() {
            fixable.push(status);
        }
    }
    if !ready.is_empty() {
        println!("\nReady to execute: {}.", ready.join(", "));
        println!("Next: agentrouter route \"your task here\"");
        return Ok(0);
    }
    println!("\nNo execution host is ready — routing still works, execution does not.");
    fixable.sort_by_key(agentrouter_hosts::fix_cost);
    if let Some(status) = fixable.first() {
        if let Some(remedy) = &status.remedy {
            println!("Easiest fix ({}): {remedy}", status.host);
        }
    }
    println!("Then re-check with: agentrouter hosts doctor");
    Ok(1)
}

fn hosts_show(home: &Path, host: &str) -> Result<i32, String> {
    let status = agentrouter_hosts::detect_host(host, None);
    println!(
        "{host}: {} ({}) - {}",
        status.state, status.availability, status.reason
    );
    if let Some(remedy) = &status.remedy {
        println!("Next: {remedy}");
    }
    let models = load_catalog(home)?;
    let targeting = models
        .iter()
        .filter(|model| {
            model
                .execution_targets
                .iter()
                .any(|target| target.host == host)
        })
        .map(ModelEntry::key)
        .collect::<Vec<_>>();
    println!(
        "Models using this host: {}",
        if targeting.is_empty() {
            "none".to_owned()
        } else {
            targeting.join(", ")
        }
    );
    Ok(0)
}

fn models_list(home: &Path, available_only: bool) -> Result<i32, String> {
    let mut models = load_catalog(home)?;
    models.sort_by(|left, right| {
        left.vendor()
            .cmp(right.vendor())
            .then_with(|| left.model_id.cmp(&right.model_id))
    });
    for model in models {
        let route = agentrouter_hosts::resolve_execution_route(&model, true);
        let availability = route
            .status
            .as_ref()
            .map(|status| status.availability.as_str())
            .unwrap_or("unknown");
        if available_only && availability != agentrouter_hosts::AVAILABLE {
            continue;
        }
        println!(
            "{:<34} {:<8} host={:<12} ability(c/r/w)={}/{}/{}",
            model.vendor_key(),
            format!("{:?}", model.release_channel).to_lowercase(),
            availability,
            model.ability.coding,
            model.ability.reasoning,
            model.ability.writing
        );
    }
    Ok(0)
}

fn models_show(home: &Path, key: &str) -> Result<i32, String> {
    let models = load_catalog(home)?;
    let model = models
        .iter()
        .find(|model| model.vendor_key() == key || model.key() == key)
        .ok_or_else(|| format!("No model '{key}'. Try: agentrouter models list"))?;
    println!("{}  ({})", model.name(), model.vendor_key());
    println!(
        "  family={}  release={}  snapshot={}",
        option_text(model.family.as_deref()),
        format!("{:?}", model.release_channel).to_lowercase(),
        format!("{:?}", model.snapshot_type).to_lowercase()
    );
    println!(
        "  context={}  max_output={}  pricing_tier={}",
        grouped(model.context_window),
        grouped(model.max_output_tokens),
        format!("{:?}", model.pricing_tier).to_lowercase()
    );
    println!(
        "  ability c/r/w = {}/{}/{} (source={}, confidence={})",
        model.ability.coding,
        model.ability.reasoning,
        model.ability.writing,
        format!("{:?}", model.ability_source).to_lowercase(),
        model
            .ability_confidence
            .map(|value| value.to_string())
            .unwrap_or_else(|| "None".to_owned())
    );
    println!(
        "  source={}  verified={}",
        option_text(model.source.as_deref()),
        option_text(model.last_verified.as_deref())
    );
    println!("  execution targets:");
    for target in &model.execution_targets {
        let status = agentrouter_hosts::target_status(target);
        println!(
            "    - {:<14} {:<7} {:<12} {}",
            target.host,
            format!("{:?}", target.execution_mode).to_lowercase(),
            status.availability,
            status.reason
        );
    }
    Ok(0)
}

fn feedback(home: &Path, args: &[String]) -> Result<i32, String> {
    let id = args
        .first()
        .ok_or_else(|| "feedback needs a decision id".to_owned())?;
    let mut rating = None;
    let mut note = String::new();
    let mut rest = args.iter().skip(1);
    while let Some(arg) = rest.next() {
        match arg.as_str() {
            "--rating" => {
                rating = Some(
                    rest.next()
                        .ok_or("--rating needs a value")?
                        .parse::<i64>()
                        .map_err(|_| "--rating must be an integer from 1 to 5".to_owned())?,
                )
            }
            "--note" => note = rest.next().ok_or("--note needs a value")?.clone(),
            option => return Err(format!("unknown feedback option '{option}'")),
        }
    }
    let rating = rating.ok_or_else(|| "feedback requires --rating 1..5".to_owned())?;
    if !(1..=5).contains(&rating) {
        return Err("--rating must be an integer from 1 to 5".to_owned());
    }
    let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
    if !agentrouter_storage::record_feedback(&connection, id, rating, &note)
        .map_err(|error| error.to_string())?
    {
        eprintln!("No decision found with id '{id}'.");
        let recent =
            agentrouter_storage::recent_ids(&connection, 5).map_err(|error| error.to_string())?;
        if !recent.is_empty() {
            eprintln!("Next: try a recent id: {}", recent.join(", "));
        }
        return Ok(2);
    }
    println!(
        "Recorded rating {rating} for {id}. Low ratings (<=2) nudge future routing toward capability, within bounds; set learning: false in config.yaml to disable."
    );
    Ok(0)
}

fn stats(home: &Path, args: &[String]) -> Result<i32, String> {
    let json_output = match args {
        [] => false,
        [flag] if flag == "--json" => true,
        _ => return Err("usage: agentrouter stats [--json]".to_owned()),
    };
    let database = home.join("agentrouter.db");
    if !database.is_file() {
        eprintln!("No decision log found at {}.", database.display());
        eprintln!("Next: agentrouter init, then agentrouter route \"<task>\"");
        return Ok(2);
    }
    let models = load_catalog(home)?;
    let tiers: HashMap<String, String> = models
        .into_iter()
        .map(|model| {
            (
                model.key(),
                format!("{:?}", model.pricing_tier).to_lowercase(),
            )
        })
        .collect();
    let connection = agentrouter_storage::connect(home).map_err(|error| error.to_string())?;
    let aggregate = agentrouter_storage::aggregate_stats(&connection, Some(&tiers))
        .map_err(|error| error.to_string())?;
    if json_output {
        println!(
            "{}",
            serde_json::to_string_pretty(&aggregate).map_err(|error| error.to_string())?
        );
        return Ok(0);
    }
    let summary = |key: &str| {
        aggregate[key]
            .as_object()
            .map(|values| {
                let mut pairs = values
                    .iter()
                    .map(|(name, value)| format!("{name}={}", value.as_i64().unwrap_or_default()))
                    .collect::<Vec<_>>();
                pairs.sort();
                if pairs.is_empty() {
                    "-".to_owned()
                } else {
                    pairs.join(", ")
                }
            })
            .unwrap_or_else(|| "-".to_owned())
    };
    println!("Decisions logged: {}", aggregate["decisions"]);
    println!("By risk: {}", summary("by_risk"));
    println!(
        "By recommended pricing tier: {}",
        summary("by_pricing_tier")
    );
    println!("By user: {}", summary("by_user"));
    let avg = aggregate["feedback"]["avg_rating"]
        .as_f64()
        .map(|value| value.to_string())
        .unwrap_or_else(|| "-".to_owned());
    let acceptance = aggregate["feedback"]["acceptance_rate"]
        .as_f64()
        .map(|value| value.to_string())
        .unwrap_or_else(|| "-".to_owned());
    println!(
        "Feedback: {} rating(s), avg {avg}, acceptance rate {acceptance}",
        aggregate["feedback"]["count"]
    );
    Ok(0)
}

fn providers_rollback(home: &Path, provider: &str) -> Result<i32, String> {
    let registry = home.join("registry");
    match agentrouter_registry::catalog_ops::rollback(&registry, provider) {
        Ok(Some(backup)) => {
            println!(
                "Rolled back '{provider}'; backed up to {}.",
                backup.file_name().unwrap_or_default().to_string_lossy()
            );
            println!("Manual models.yaml is now authoritative. Re-refresh to restore, or");
            println!("Next: agentrouter providers restore {provider}");
            Ok(0)
        }
        Ok(None) => {
            eprintln!("No generated catalog for '{provider}' to roll back.");
            eprintln!(
                "Why: {} does not exist.",
                registry
                    .join(format!("models.{provider}.generated.yaml"))
                    .display()
            );
            Ok(2)
        }
        Err(error) => Err(format!("Cannot roll back: {error}")),
    }
}

fn providers_restore(home: &Path, provider: &str) -> Result<i32, String> {
    let registry = home.join("registry");
    match agentrouter_registry::catalog_ops::restore(&registry, provider) {
        Ok(Some(restored)) => {
            println!("Restored {}.", restored.display());
            println!("Next: agentrouter providers status");
            Ok(0)
        }
        Ok(None) => {
            eprintln!("No rollback backup for '{provider}' to restore.");
            eprintln!(
                "Why: {} does not exist.",
                registry
                    .join(format!("models.{provider}.generated.yaml.bak"))
                    .display()
            );
            Ok(2)
        }
        Err(error) => Err(format!("Cannot restore '{provider}': {error}")),
    }
}

fn providers_doctor(home: &Path) -> Result<i32, String> {
    let registry = home.join("registry");
    if !registry.is_dir() {
        eprintln!("Registry directory not found: {}", registry.display());
        eprintln!("Next: run agentrouter init first.");
        return Ok(3);
    }
    let mut generated = std::fs::read_dir(&registry)
        .map_err(|error| error.to_string())?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| {
                    name.starts_with("models.") && name.ends_with(".generated.yaml")
                })
        })
        .collect::<Vec<_>>();
    generated.sort();
    if generated.is_empty() {
        println!("No refreshed catalogs to check. Manual models.yaml is authoritative.");
        return Ok(0);
    }
    let providers = load_providers(&registry.join("providers.yaml"))
        .map_err(|error| format!("Cannot validate: {error}"))?;
    let today = chrono::Local::now().date_naive();
    let mut broken = 0;
    for path in generated {
        let provider = path
            .file_name()
            .and_then(|name| name.to_str())
            .and_then(|name| name.strip_prefix("models."))
            .and_then(|name| name.strip_suffix(".generated.yaml"))
            .unwrap_or("unknown");
        let status = agentrouter_registry::catalog_ops::read_status(&path, today);
        let models =
            agentrouter_registry::load_models(&path, &providers).map_err(|error| error.to_string());
        match (status, models) {
            (Ok(status), Ok(_)) => {
                println!(
                    "[{}] {}",
                    if status.stale { "STALE" } else { "OK   " },
                    status.summary()
                );
            }
            (Err(error), _) | (_, Err(error)) => {
                println!("[FAIL ] {provider:<12} {error}");
                broken += 1;
            }
        }
    }
    if broken > 0 {
        println!("\n{broken} generated catalog(s) are corrupt or invalid.");
        println!("Next: agentrouter providers rollback <provider>, then re-refresh.");
        Ok(3)
    } else {
        Ok(0)
    }
}

fn providers_refresh(home: &Path, args: &[String]) -> Result<i32, String> {
    let mut provider = None;
    let mut limit = 25_usize;
    let mut match_id = None;
    let mut dry_run = false;
    let mut rest = args.iter();
    while let Some(arg) = rest.next() {
        match arg.as_str() {
            "--limit" => {
                limit = rest
                    .next()
                    .ok_or("--limit needs a positive integer")?
                    .parse::<usize>()
                    .map_err(|_| "--limit needs a positive integer")?;
                if limit == 0 {
                    return Err("--limit needs a positive integer".to_owned());
                }
            }
            "--match" => match_id = Some(rest.next().ok_or("--match needs text")?.clone()),
            "--dry-run" => dry_run = true,
            value if !value.starts_with('-') && provider.is_none() => {
                provider = Some(value.to_owned())
            }
            _ => {
                return Err(
                    "usage: agentrouter providers refresh [openrouter|openai] [--limit N] [--match TEXT] [--dry-run]"
                        .to_owned(),
                )
            }
        }
    }
    let provider = provider.unwrap_or_else(|| "openrouter".to_owned());
    let supported = ["openrouter", "openai"];
    if !supported.contains(&provider.as_str()) {
        eprintln!("Provider '{provider}' is not refreshable in this build.");
        eprintln!(
            "Why: only these adapters have live refresh: {}.",
            supported.join(", ")
        );
        eprintln!(
            "Next: agentrouter providers refresh openrouter, or edit {} by hand.",
            home.join("registry").join("models.yaml").display()
        );
        return Ok(2);
    }
    let registry = home.join("registry");
    if !registry.is_dir() {
        eprintln!("Registry directory not found: {}", registry.display());
        eprintln!("Why: refresh writes next to your manual registry.");
        eprintln!("Next: run agentrouter init first.");
        return Ok(3);
    }
    let key_env = if provider == "openai" {
        "OPENAI_API_KEY"
    } else {
        "OPENROUTER_API_KEY"
    };
    let key_present = env::var(key_env).is_ok_and(|key| !key.is_empty());
    if key_present {
        println!("auth: using {key_env} from environment");
    } else if provider == "openrouter" {
        println!("auth: no {key_env} set - using the public catalog endpoint");
    } else {
        println!("auth: no {key_env} set");
    }
    let result = match agentrouter_cli::providers::fetch_catalog(
        &provider,
        limit,
        match_id.as_deref(),
    ) {
        Ok(result) => result,
        Err(error) => {
            eprintln!("Refresh failed: {error}");
            eprintln!(
                "Why: the live catalog could not be fetched or parsed; your registry was NOT modified."
            );
            eprintln!(
                "Next: check your network, retry later, or keep using the manual registry (models.yaml) - routing works without refresh."
            );
            return Ok(1);
        }
    };
    for warning in &result.warnings {
        eprintln!("warning: {warning}");
    }
    println!("Fetched {} models from {}:", result.entries.len(), provider);
    for entry in &result.entries {
        println!(
            "  {:<52} ctx {:>9}  {}",
            entry.key(),
            entry.context_window,
            format!("{:?}", entry.pricing_tier).to_lowercase()
        );
    }
    let previous = agentrouter_cli::providers::previous_model_ids(&registry, &provider);
    let current = result
        .entries
        .iter()
        .map(|entry| entry.model_id.clone())
        .collect::<std::collections::HashSet<_>>();
    let deprecations = agentrouter_registry::catalog_ops::deprecations(&previous, &current);
    if !deprecations.is_empty() {
        println!(
            "\n{} candidate deprecation(s) — in the previous generated catalog but not in this fetch (reported only; nothing is deleted):",
            deprecations.len()
        );
        for model_id in &deprecations {
            println!("  {model_id}");
        }
    }
    if dry_run {
        println!("\nDry run - nothing written.");
        return Ok(0);
    }
    let path = agentrouter_cli::providers::write_generated_catalog(
        &registry,
        &provider,
        result.source_url,
        &result.entries,
        limit,
        match_id.as_deref(),
    )?;
    println!("\nWrote {}", path.display());
    println!(
        "Manual models.yaml is untouched and wins on collision. Delete models.{provider}.generated.yaml to revert."
    );
    println!("Next: agentrouter registry list");
    Ok(0)
}

fn server(home: &Path, args: &[String]) -> Result<i32, String> {
    if args
        .iter()
        .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
    {
        println!("Usage: agentrouter server [--host HOST] [--port PORT]");
        return Ok(0);
    }
    let mut host = "127.0.0.1".to_owned();
    let mut port = 8000_u16;
    let mut rest = args.iter();
    while let Some(argument) = rest.next() {
        match argument.as_str() {
            "--host" => host = rest.next().ok_or("--host requires a value")?.clone(),
            "--port" => {
                port = rest
                    .next()
                    .ok_or("--port requires an integer from 0 to 65535")?
                    .parse::<u16>()
                    .map_err(|_| "--port requires an integer from 0 to 65535")?;
            }
            _ => return Err("usage: agentrouter server [--host HOST] [--port PORT]".to_owned()),
        }
    }
    let bind = if host.starts_with('[') || !host.contains(':') {
        format!("{host}:{port}")
    } else {
        format!("[{host}]:{port}")
    };
    agentrouter_api::server::run(bind, home.to_path_buf())
        .map(|()| 0)
        .map_err(|error| error.to_string())
}

fn mcp(home: &Path, args: &[String]) -> Result<i32, String> {
    if args
        .iter()
        .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
    {
        println!("Usage: agentrouter mcp (stdio server)");
        return Ok(0);
    }
    if !args.is_empty() {
        return Err("usage: agentrouter mcp".to_owned());
    }
    agentrouter_mcp::run_stdio(&agentrouter_mcp::Server::new(home.to_path_buf()))
        .map(|()| 0)
        .map_err(|error| error.to_string())
}

fn run() -> Result<i32, String> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        println!("{}", usage());
        return Ok(0);
    };
    if matches!(command.as_str(), "-h" | "--help" | "help") {
        println!("{}", usage());
        return Ok(0);
    }
    if command == "--version" || command == "-V" {
        println!("agentrouter {}", agentrouter_core::package_version());
        return Ok(0);
    }
    let tail = args.collect::<Vec<_>>();
    if command == "dataset" {
        return agentrouter_evaluation::annotation_cli::run(tail.into_iter());
    }
    if command == "eval" {
        let executable = sibling_executable("agentrouter-evaluate")?;
        let status = Command::new(executable)
            .args(tail)
            .status()
            .map_err(|error| error.to_string())?;
        return Ok(status.code().unwrap_or(1));
    }

    let home = home()?;
    match command.as_str() {
        "init" => run_sibling("init_cli", with_home(&home, tail)),
        "route" => {
            if tail.is_empty() {
                return Err("route needs a task prompt".to_owned());
            }
            let route_args = tail.into_iter().filter(|arg| arg != "--json");
            run_sibling("cli_route_cli", with_home(&home, route_args))
        }
        "explain" => {
            let id = tail
                .first()
                .ok_or_else(|| "explain needs a decision id".to_owned())?;
            run_sibling(
                "decision_cli",
                with_home(&home, ["explain".to_owned(), id.clone()]),
            )
        }
        "feedback" => feedback(&home, &tail),
        "stats" => stats(&home, &tail),
        "prompt" => {
            if tail.first().map(String::as_str) != Some("generate") {
                return Err(
                    "usage: agentrouter prompt generate --from <decision-id> [--tool <host>]"
                        .to_owned(),
                );
            }
            let mut id = None;
            let mut tool = None;
            let mut rest = tail.into_iter().skip(1);
            while let Some(arg) = rest.next() {
                match arg.as_str() {
                    "--from" => id = rest.next(),
                    "--tool" => tool = rest.next(),
                    option => return Err(format!("unknown prompt option '{option}'")),
                }
            }
            let id =
                id.ok_or_else(|| "prompt generate requires --from <decision-id>".to_owned())?;
            let mut forwarded = vec!["prompt".to_owned(), id];
            if let Some(tool) = tool {
                forwarded.push(tool);
            }
            run_sibling("decision_cli", with_home(&home, forwarded))
        }
        "registry" => {
            if tail.first().map(String::as_str) != Some("list") {
                return Err("usage: agentrouter registry list [options]".to_owned());
            }
            run_sibling("registry_cli", with_home(&home, tail.into_iter().skip(1)))
        }
        "providers" => match tail.first().map(String::as_str) {
            Some("status") if tail.len() == 1 => run_sibling(
                "providers_status_cli",
                [home.to_string_lossy().into_owned()],
            ),
            Some("doctor") if tail.len() == 1 => providers_doctor(&home),
            Some("refresh") => providers_refresh(&home, &tail[1..]),
            Some("rollback") if tail.len() == 2 => providers_rollback(&home, &tail[1]),
            Some("restore") if tail.len() == 2 => providers_restore(&home, &tail[1]),
            _ => Err(
                "usage: agentrouter providers <status|doctor|rollback PROVIDER|restore PROVIDER>"
                    .to_owned(),
            ),
        },
        "hosts" => match tail.first().map(String::as_str) {
            Some("list") if tail.len() == 1 => hosts_list(&home),
            Some("doctor") if tail.len() == 1 => hosts_doctor(),
            Some("show") if tail.len() == 2 => hosts_show(&home, &tail[1]),
            _ => Err("usage: agentrouter hosts <list|doctor|show HOST>".to_owned()),
        },
        "models" => match tail.first().map(String::as_str) {
            Some("list") => {
                let available_only = tail.iter().skip(1).try_fold(false, |_found, arg| {
                    if arg == "--available" {
                        Ok(true)
                    } else {
                        Err(format!("unknown models list option '{arg}'"))
                    }
                })?;
                models_list(&home, available_only)
            }
            Some("show") if tail.len() == 2 => models_show(&home, &tail[1]),
            _ => Err("usage: agentrouter models <list [--available]|show KEY>".to_owned()),
        },
        "doctor" => run_sibling("doctor_cli", with_home(&home, tail)),
        "server" => server(&home, &tail),
        "mcp" => mcp(&home, &tail),
        "dashboard" => run_sibling("dashboard_cli", with_home(&home, tail)),
        _ => Err(format!(
            "unknown or not-yet-ported command '{command}'\n{}",
            usage()
        )),
    }
}

fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
