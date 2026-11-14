//! Unified Rust command entry point for the AgentRouter commands migrated so far.
//!
//! This binary dispatches to sibling compatibility executables installed by
//! the same Cargo package. The annotation workflow is linked directly from the
//! evaluation crate so it does not depend on a second package installation.

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::env;
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

use agentrouter_registry::{load_all_models, load_providers, ModelEntry};

fn usage() -> &'static str {
    "usage: agentrouter <init|setup|route|explain|feedback|execute|stats|evaluate|prompt|registry|providers|hosts|models|doctor|server|mcp|dashboard|plugin|dataset|eval> [options]\n\nRust commands currently available:\n  init [--force]\n  setup [--preference quality|balanced|cheap|fast] [--sample TEXT]\n  route <task> [preference] [routing controls] [--json]\n  explain <decision-id>\n  feedback <decision-id> --rating 1..5 [--note TEXT]\n  execute <decision-id> [--yes] [--dry-run]\n  stats [--json]\n  evaluate [--gold PATH] [--out-dir PATH] [--json] [--no-artifacts]\n  prompt generate --from <decision-id> [--tool <host>]\n  registry list [options]\n  providers <status|doctor|refresh [PROVIDER] [--limit N] [--match TEXT] [--dry-run]|rollback PROVIDER|restore PROVIDER>\n  hosts <list|doctor|show HOST>\n  models <list|show KEY>\n  doctor [options]\n  server [--host HOST] [--port PORT]\n  mcp (stdio server)\n  dashboard [port]\n  plugin <list|install NAME [--dry-run] [--force] [--adopt-identical]|uninstall NAME|doctor [--json]>\n  dataset <annotation workflow command>\n  eval <evaluation command> (requires agentrouter-evaluate installed)"
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

fn write_setup_preference(home: &Path, preference: &str) -> Result<(), String> {
    let preferences = agentrouter_policy::preference_weights();
    let weights = preferences
        .get(preference)
        .ok_or_else(|| format!("unknown routing preference {preference}"))?;
    let home_dir = cap_std::fs::Dir::open_ambient_dir(home, cap_std::ambient_authority())
        .map_err(|error| format!("could not open AgentRouter home: {error}"))?;
    let home_file = home_dir
        .try_clone()
        .map_err(|error| format!("could not inspect AgentRouter home: {error}"))?
        .into_std_file();
    let mut options = fs_at::OpenOptions::default();
    options
        .read(true)
        .write(fs_at::OpenOptionsWriteMode::Write)
        .create(true)
        .follow(false);
    let mut file = options
        .open_at(&home_file, Path::new("config.yaml"))
        .map_err(|error| format!("could not open config.yaml safely: {error}"))?;
    let metadata = file
        .metadata()
        .map_err(|error| format!("could not inspect config.yaml: {error}"))?;
    if !metadata.is_file() || metadata.file_type().is_symlink() {
        return Err("config.yaml must be a regular, unlinked file".to_owned());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if metadata.nlink() > 1 {
            return Err("config.yaml has multiple hard links; refusing to overwrite it".to_owned());
        }
    }
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Foundation::HANDLE;
        use windows_sys::Win32::Storage::FileSystem::{
            GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
        };

        let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
        let handle: HANDLE = file.as_raw_handle();
        // SAFETY: `file` owns a valid handle for the call, and the Win32 API
        // initializes `information` on success before we read its attributes.
        if unsafe { GetFileInformationByHandle(handle, information.as_mut_ptr()) } == 0 {
            return Err(format!(
                "could not verify config.yaml file links: {}",
                std::io::Error::last_os_error()
            ));
        }
        // SAFETY: the successful API call above initialized the structure.
        let information = unsafe { information.assume_init() };
        if information.nNumberOfLinks > 1 || information.dwFileAttributes & 0x400 != 0 {
            return Err(
                "config.yaml is linked or reparse-pointed; refusing to overwrite it".to_owned(),
            );
        }
    }

    let mut contents = String::new();
    file.read_to_string(&mut contents)
        .map_err(|error| format!("could not read config.yaml: {error}"))?;
    let mut config: serde_yaml::Value = if contents.trim().is_empty() {
        serde_yaml::Value::Mapping(serde_yaml::Mapping::new())
    } else {
        serde_yaml::from_str(&contents)
            .map_err(|error| format!("Config error: invalid YAML in config.yaml: {error}"))?
    };
    if config.is_null() {
        config = serde_yaml::Value::Mapping(serde_yaml::Mapping::new());
    }
    let mapping = config
        .as_mapping_mut()
        .ok_or_else(|| "Config error: config.yaml must be a YAML mapping.".to_owned())?;
    let mut preference_mapping = serde_yaml::Mapping::new();
    for name in ["w_cap", "w_cost", "w_lat", "w_ctx"] {
        let value = weights
            .get(name)
            .ok_or_else(|| format!("routing preference {preference} is missing {name}"))?;
        preference_mapping.insert(
            name,
            serde_yaml::to_value(value).map_err(|error| error.to_string())?,
        );
    }
    mapping.insert("weights", serde_yaml::Value::Mapping(preference_mapping));
    let rendered = serde_yaml::to_string(&config).map_err(|error| error.to_string())?;
    file.set_len(0)
        .map_err(|error| format!("could not update config.yaml: {error}"))?;
    file.seek(SeekFrom::Start(0))
        .map_err(|error| format!("could not update config.yaml: {error}"))?;
    file.write_all(rendered.as_bytes())
        .map_err(|error| format!("could not update config.yaml: {error}"))
}

fn setup(home: &Path, args: &[String]) -> Result<i32, String> {
    if args
        .iter()
        .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
    {
        println!(
            "Usage: agentrouter setup [--preference quality|balanced|cheap|fast] [--sample TEXT]"
        );
        return Ok(0);
    }
    let mut preference = "balanced".to_owned();
    let mut sample = "summarize this PDF and list the action items".to_owned();
    let mut args = args.iter();
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--preference" => {
                preference = args.next().ok_or("--preference needs a value")?.clone();
            }
            "--sample" => sample = args.next().ok_or("--sample needs text")?.clone(),
            unknown => return Err(format!("unknown setup option '{unknown}'")),
        }
    }
    const PREFERENCE_ORDER: [&str; 4] = ["quality", "cheap", "fast", "balanced"];
    let available_preferences = agentrouter_policy::preference_weights();
    if !available_preferences.contains_key(preference.as_str()) {
        eprintln!(
            "Unknown --preference '{preference}'. Choose: {}.",
            PREFERENCE_ORDER.join(", ")
        );
        return Ok(2);
    }

    println!("AgentRouter setup - everything runs locally; no task text leaves this machine.\n");
    println!("1. Home directory");
    for line in agentrouter_cli::init_home_with_force(home, false)? {
        println!("{line}");
    }

    println!("\n2. Execution hosts (credentials detected by presence only; values never read)");
    let mut real_available = 0;
    for host in agentrouter_hosts::known_hosts() {
        let status = agentrouter_hosts::detect_host(host, None);
        let mark = if status.availability == agentrouter_hosts::AVAILABLE {
            "OK "
        } else {
            "-- "
        };
        println!(
            "   [{mark}] {host:<16} {:<14} {}",
            status.state, status.reason
        );
        if host != "manual" && status.availability == agentrouter_hosts::AVAILABLE {
            real_available += 1;
        }
    }
    if real_available == 0 {
        println!("   Note: no host available yet - install Claude Code/Codex or set an API key.");
        println!("   Run 'agentrouter hosts doctor' for the exact next step per host.");
    }

    println!("\n3. Preference: {preference}");
    write_setup_preference(home, &preference)?;
    println!(
        "   Saved scoring weights to {}",
        home.join("config.yaml").display()
    );

    println!("\n4. Sample route: \"{sample}\"");
    let models = load_catalog(home)?;
    let (weights, _learning, max_tier) = agentrouter_cli::load_route_config(home)
        .map_err(|error| format!("Config error: {error}"))?;
    let models = agentrouter_cli::apply_policy(models, max_tier.as_deref())?;
    let classification = agentrouter_classifier::classify(
        &sample,
        &agentrouter_classifier::ClassifyOptions::default(),
    );
    let route =
        agentrouter_cli::route_payload(&sample, &models, &classification, weights, None, None);
    if route["recommendation"].is_object() {
        println!(
            "   -> {}  (score {:.2})",
            route["recommendation"]["model"]
                .as_str()
                .unwrap_or_default(),
            route["recommendation"]["score"]
                .as_f64()
                .unwrap_or_default()
        );
    } else {
        println!("   -> no eligible model (check your registry)");
    }

    println!("\n5. Install a host integration:");
    println!("   agentrouter plugin install claude-code    # or: codex");
    println!("\nDone. Next: agentrouter route \"<your task>\"");
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
        let status = agentrouter_registry::catalog_ops::read_status(&path, today)
            .map_err(|error| error.to_string());
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

fn plugin_roots() -> Result<Vec<(&'static agentrouter_cli::plugins::PluginSpec, PathBuf)>, String> {
    let override_root = env::var_os("AGENTROUTER_PLUGIN_ROOT").map(PathBuf::from);
    #[cfg(windows)]
    let user_home = env::var_os("USERPROFILE")
        .or_else(|| {
            let drive = env::var_os("HOMEDRIVE")?;
            let path = env::var_os("HOMEPATH")?;
            let mut joined = PathBuf::from(drive);
            joined.push(path);
            Some(joined.into_os_string())
        })
        .or_else(|| env::var_os("HOME"));
    #[cfg(not(windows))]
    let user_home = env::var_os("HOME");
    let home = user_home.map(PathBuf::from);
    if override_root.is_none() && home.is_none() {
        return Err(
            "Set AGENTROUTER_PLUGIN_ROOT or HOME to locate plugin destinations.".to_owned(),
        );
    }
    agentrouter_cli::plugins::known_plugins()
        .iter()
        .map(|plugin| {
            let root = agentrouter_cli::plugins::dest_root(
                plugin,
                override_root.as_deref(),
                home.as_deref(),
            )?;
            Ok((plugin, root))
        })
        .collect()
}

fn plugin_list() -> Result<i32, String> {
    for (plugin, root) in plugin_roots()? {
        println!(
            "{:<12} [{}]  {}",
            plugin.name,
            agentrouter_cli::plugins::status(plugin, &root),
            plugin.description
        );
    }
    Ok(0)
}

fn plugin_install(args: &[String]) -> Result<i32, String> {
    let mut name = None;
    let mut dry_run = false;
    let mut force = false;
    let mut adopt_identical = false;
    for argument in args.iter().skip(1) {
        match argument.as_str() {
            "--dry-run" => dry_run = true,
            "--adopt-identical" => adopt_identical = true,
            "--force" => force = true,
            option if option.starts_with('-') => {
                return Err(format!("unknown plugin install option: {option}"));
            }
            value if name.is_none() => name = Some(value),
            value => return Err(format!("unexpected plugin install argument: {value}")),
        }
    }
    let name = name.ok_or_else(|| {
        "usage: agentrouter plugin install NAME [--dry-run] [--force] [--adopt-identical]"
            .to_owned()
    })?;
    let plugin = agentrouter_cli::plugins::get_plugin(name)?;
    let root = plugin_roots()?
        .into_iter()
        .find(|(candidate, _)| candidate.name == plugin.name)
        .map(|(_, root)| root)
        .ok_or_else(|| "plugin destination root is unavailable".to_owned())?;
    if dry_run {
        let plan = agentrouter_cli::plugins::plan(plugin, &root, adopt_identical)?;
        println!("Would install '{}':", plugin.name);
        for item in plan {
            let action = item
                .get("action")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("blocked");
            let destination = item
                .get("dest")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            println!("  {action:<24} {destination}");
        }
    } else {
        let results = agentrouter_cli::plugins::install(plugin, &root, force, adopt_identical)?;
        for result in results {
            let name = result
                .get("result")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("blocked");
            let destination = result
                .get("dest")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            println!("  {name:<28} {destination}");
        }
        println!(
            "Installed '{}'. Uninstall with: agentrouter plugin uninstall {}",
            plugin.name, plugin.name
        );
    }
    Ok(0)
}

fn plugin_uninstall(args: &[String]) -> Result<i32, String> {
    let mut names = args.iter().skip(1);
    let name = names
        .next()
        .ok_or_else(|| "usage: agentrouter plugin uninstall NAME".to_owned())?;
    if let Some(extra) = names.next() {
        return Err(format!("unexpected plugin uninstall argument: {extra}"));
    }
    let plugin = agentrouter_cli::plugins::get_plugin(name)?;
    let root = plugin_roots()?
        .into_iter()
        .find(|(candidate, _)| candidate.name == plugin.name)
        .map(|(_, root)| root)
        .ok_or_else(|| "plugin destination root is unavailable".to_owned())?;
    for result in agentrouter_cli::plugins::uninstall(plugin, &root)? {
        let name = result
            .get("result")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("blocked");
        let destination = result
            .get("dest")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        println!("  {name:<28} {destination}");
    }
    Ok(0)
}

fn plugin_doctor(as_json: bool) -> Result<i32, String> {
    let roots = plugin_roots()?;
    let findings = roots
        .iter()
        .flat_map(|(plugin, root)| agentrouter_cli::plugins::diagnose(plugin, root))
        .collect::<Vec<_>>();
    let overall = if findings
        .iter()
        .any(|finding| finding.get("status").and_then(serde_json::Value::as_str) == Some("blocked"))
    {
        "blocked"
    } else if findings.iter().any(|finding| {
        finding.get("status").and_then(serde_json::Value::as_str) == Some("attention")
    }) {
        "attention"
    } else {
        "ok"
    };
    if as_json {
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "status": overall,
                "findings": findings,
            }))
            .map_err(|error| error.to_string())?
        );
    } else {
        for (plugin, root) in &roots {
            println!(
                "{}: {}  (root: {})",
                plugin.name,
                agentrouter_cli::plugins::status(plugin, root),
                root.display()
            );
            for finding in findings.iter().filter(|finding| {
                finding.get("plugin").and_then(serde_json::Value::as_str) == Some(plugin.name)
            }) {
                let status = finding
                    .get("status")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("blocked");
                let mark = match status {
                    "ok" => "OK  ",
                    "attention" => "NOTE",
                    _ => "STOP",
                };
                let location = finding
                    .get("dest")
                    .or_else(|| finding.get("check"))
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("diagnose");
                println!("  [{mark}] {location}");
                if let Some(summary) = finding.get("summary").and_then(serde_json::Value::as_str) {
                    println!("         {summary}");
                }
                if let Some(remedy) = finding.get("remedy").and_then(serde_json::Value::as_str) {
                    println!("         -> {remedy}");
                }
            }
        }
    }
    match overall {
        "blocked" => Ok(1),
        "attention" => Ok(2),
        _ => Ok(0),
    }
}

fn plugin(args: &[String]) -> Result<i32, String> {
    if args
        .iter()
        .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
    {
        println!("Usage: agentrouter plugin <list|install NAME [--dry-run] [--force] [--adopt-identical]|uninstall NAME|doctor [--json]>");
        return Ok(0);
    }
    match args {
        [command] if command == "list" => plugin_list(),
        [command, ..] if command == "install" => plugin_install(args),
        [command, ..] if command == "uninstall" => plugin_uninstall(args),
        [command] if command == "doctor" => plugin_doctor(false),
        [command, flag] if command == "doctor" && flag == "--json" => plugin_doctor(true),
        _ => Err("usage: agentrouter plugin list".to_owned()),
    }
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
    if command == "evaluate" {
        if tail
            .iter()
            .any(|argument| matches!(argument.as_str(), "--help" | "-h"))
        {
            println!("Usage: agentrouter evaluate [--gold PATH] [--out-dir PATH] [--json] [--no-artifacts]");
            return Ok(0);
        }
        return run_sibling(
            "agentrouter-evaluate",
            std::iter::once("legacy-gold".to_owned()).chain(tail),
        );
    }
    if command == "plugin" {
        return plugin(&tail);
    }
    if command == "setup" {
        let home = home()?;
        return setup(&home, &tail);
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
        "execute" => agentrouter_cli::execution::run(&home, &tail),
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
