//! Unified Rust command entry point for the AgentRouter commands migrated so far.
//!
//! This binary dispatches to sibling compatibility executables installed by
//! the same Cargo package. The annotation workflow is linked directly from the
//! evaluation crate so it does not depend on a second package installation.

use std::collections::BTreeMap;
use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;

use agentrouter_registry::{load_all_models, load_providers, ModelEntry};

fn usage() -> &'static str {
    "usage: agentrouter <init|route|explain|feedback|prompt|registry|providers|hosts|models|doctor|dashboard|dataset|eval> [options]\n\nRust commands currently available:\n  init [--force]\n  route <task> [preference] [routing controls] [--json]\n  explain <decision-id>\n  feedback <decision-id> --rating 1..5 [--note TEXT]\n  prompt generate --from <decision-id> [--tool <host>]\n  registry list [options]\n  providers status\n  hosts <list|doctor|show HOST>\n  models <list|show KEY>\n  doctor [options]\n  dashboard [port]\n  dataset <annotation workflow command>\n  eval <evaluation command> (requires agentrouter-evaluate installed)"
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
        "providers" => {
            if tail.first().map(String::as_str) != Some("status") || tail.len() != 1 {
                return Err("usage: agentrouter providers status".to_owned());
            }
            run_sibling(
                "providers_status_cli",
                [home.to_string_lossy().into_owned()],
            )
        }
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
