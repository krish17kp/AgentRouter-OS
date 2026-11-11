//! Rust evaluation command line for offline-first evaluation workflows.

use agentrouter_evaluation::runner::{run_registered, RegisteredRunOptions};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::process::Command;

const DEFAULT_OUT: &str = "artifacts/evaluation";

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn runtime_environment(root: &Path) -> Value {
    let git_sha = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(root)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|sha| sha.trim().to_owned())
        .filter(|sha| !sha.is_empty());
    let rustc = Command::new("rustc")
        .arg("--version")
        .output()
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|version| version.trim().to_owned());
    json!({
        "agentrouter_version": agentrouter_core::package_version(),
        "runtime": "rust",
        "rustc": rustc,
        "platform": format!("{}-{}", std::env::consts::OS, std::env::consts::ARCH),
        "git_sha": git_sha,
    })
}

fn usage() -> &'static str {
    "usage: agentrouter-evaluate <list-datasets|validate-dataset|run|report|compare|prepare|status|context-band-generalization> [options]"
}

fn parse_flag(args: &mut impl Iterator<Item = String>, flag: &str) -> Result<String, String> {
    let value = args.next().ok_or_else(|| format!("{flag} needs a value"))?;
    if value.starts_with('-') {
        return Err(format!("{flag} needs a value"));
    }
    Ok(value)
}

fn parse_i64(args: &mut impl Iterator<Item = String>, flag: &str) -> Result<i64, String> {
    parse_flag(args, flag)?
        .parse::<i64>()
        .map_err(|_| format!("invalid {flag} value"))
}

fn result_code(result: &Value) -> i32 {
    if result["release_ready"].as_bool() == Some(true) {
        0
    } else {
        1
    }
}

fn list_datasets(json_output: bool) -> Result<i32, String> {
    let root = project_root();
    let rows = agentrouter_evaluation::DATASET_NAMES
        .iter()
        .map(|name| {
            let spec = agentrouter_evaluation::registry_api::dataset_spec(name)?;
            let (availability, license) = if *name == "agentrouter-gold" {
                let description = agentrouter_evaluation::agentrouter_gold_describe(
                    &root.join("agentrouter").join(spec.metadata.source.as_str()),
                );
                (
                    description["availability"]
                        .as_str()
                        .unwrap_or("skipped_external")
                        .to_owned(),
                    spec.metadata.license,
                )
            } else {
                let path = root.join("agentrouter/evaluation/fixtures").join(
                    spec.fixture
                        .ok_or_else(|| format!("{name}: fixture path is missing"))?,
                );
                (
                    agentrouter_evaluation::adapter_availability(&path).to_owned(),
                    spec.metadata.license,
                )
            };
            Ok(json!({"name": name, "availability": availability, "license": license}))
        })
        .collect::<Result<Vec<_>, String>>()?;
    if json_output {
        println!(
            "{}",
            serde_json::to_string_pretty(&rows).map_err(|e| e.to_string())?
        );
    } else {
        for row in rows {
            println!(
                "{:<16} {:<16} license={}",
                row["name"].as_str().unwrap_or_default(),
                row["availability"].as_str().unwrap_or_default(),
                row["license"].as_str().unwrap_or_default()
            );
        }
    }
    Ok(0)
}

fn run_eval(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let root = project_root();
    let mut args = args;
    let mut profile = "fast".to_owned();
    let mut dataset = None;
    let mut limit = None;
    let mut seed = 0;
    let mut languages = None;
    let mut source = "fixture".to_owned();
    let mut out_dir = PathBuf::from(DEFAULT_OUT);
    let mut json_output = false;
    let mut no_artifacts = false;
    let mut measure_all = false;
    let mut require_release_ready = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--profile" => profile = parse_flag(&mut args, "--profile")?,
            "--dataset" => dataset = Some(parse_flag(&mut args, "--dataset")?),
            "--limit" => limit = Some(parse_i64(&mut args, "--limit")?),
            "--seed" => seed = parse_i64(&mut args, "--seed")?,
            "--languages" => {
                let value = parse_flag(&mut args, "--languages")?;
                languages = Some(
                    value
                        .split(',')
                        .map(|part| part.trim().to_owned())
                        .collect(),
                );
            }
            "--source" => source = parse_flag(&mut args, "--source")?,
            "--out-dir" => out_dir = PathBuf::from(parse_flag(&mut args, "--out-dir")?),
            "--json" => json_output = true,
            "--no-artifacts" => no_artifacts = true,
            "--all" => measure_all = true,
            "--require-release-ready" => require_release_ready = true,
            _ => return Err(format!("unknown option {arg}")),
        }
    }
    if !matches!(source.as_str(), "fixture" | "real") {
        return Err(format!("Invalid --source '{source}' (use fixture|real)."));
    }
    if require_release_ready && !measure_all {
        return Err("--require-release-ready requires --all.".to_owned());
    }
    let result = run_registered(RegisteredRunOptions {
        project_root: root.clone(),
        dataset,
        profile: Some(profile),
        limit,
        seed,
        source,
        languages,
        measure_all,
        commands: vec!["evaluate".to_owned()],
        groups: vec!["eval".to_owned()],
        environment: runtime_environment(&root),
    })?;
    if !no_artifacts {
        for path in agentrouter_evaluation::write_reports(&result, &out_dir)
            .map_err(|error| error.to_string())?
        {
            println!("Wrote {}", out_dir.join(path).display());
        }
    }
    if json_output {
        let mut output = result.clone();
        if let Some(object) = output.as_object_mut() {
            object.remove("classification");
        }
        println!(
            "{}",
            serde_json::to_string_pretty(&output).map_err(|error| error.to_string())?
        );
    } else {
        println!(
            "\nGrade /100: {}  (measured: {})",
            result["grade_over_100"], result["grade_of_measured"]
        );
        println!(
            "Release-ready: {}",
            if result["release_ready"].as_bool() == Some(true) {
                "YES"
            } else {
                "NO"
            }
        );
        println!("Cases: {}", result["n_cases"]);
        println!("\nDatasets:");
        if let Some(datasets) = result["datasets"].as_object() {
            for (name, info) in datasets {
                println!(
                    "  {name:<16} {:<16} n={}",
                    info["status"].as_str().unwrap_or_default(),
                    info["n"]
                );
            }
        }
        println!("\nRelease gates:");
        if let Some(gates) = result["release_gates"].as_object() {
            for (name, passed) in gates {
                println!(
                    "  [{}] {name}",
                    if passed.as_bool() == Some(true) {
                        "PASS"
                    } else {
                        "FAIL"
                    }
                );
            }
        }
    }
    if require_release_ready && result_code(&result) != 0 {
        return Ok(1);
    }
    Ok(0)
}

fn run() -> Result<i32, String> {
    let mut args = std::env::args().skip(1);
    let command = args.next().ok_or_else(|| usage().to_owned())?;
    match command.as_str() {
        "list-datasets" => {
            let json_output = args.any(|arg| arg == "--json");
            list_datasets(json_output)
        }
        "validate-dataset" => {
            let name_or_path = args
                .next()
                .ok_or_else(|| "validate-dataset needs a name or path".to_owned())?;
            let root = project_root();
            let cases = if agentrouter_evaluation::registry_api::dataset_names()
                .contains(&name_or_path.as_str())
            {
                agentrouter_evaluation::registry_api::collect(
                    &[name_or_path.as_str()],
                    &root,
                    None,
                    0,
                    "fixture",
                    None,
                )?
                .cases
            } else {
                agentrouter_evaluation::load_agentrouter_gold(Path::new(&name_or_path))?
            };
            println!("OK: {} cases validated.", cases.len());
            Ok(0)
        }
        "run" => run_eval(args),
        "report" => {
            let path = PathBuf::from(
                args.next()
                    .ok_or_else(|| "report needs a result JSON path".to_owned())?,
            );
            if !path.exists() {
                return Err(format!("Not found: {}", path.display()));
            }
            let result =
                agentrouter_evaluation::load_result(&path).map_err(|error| error.to_string())?;
            print!("{}", agentrouter_evaluation::render_markdown(&result));
            Ok(0)
        }
        "compare" => {
            let baseline = PathBuf::from(
                args.next()
                    .ok_or_else(|| "compare needs a baseline path".to_owned())?,
            );
            let current = PathBuf::from(
                args.next()
                    .ok_or_else(|| "compare needs a current path".to_owned())?,
            );
            let mut out_dir = PathBuf::from(DEFAULT_OUT);
            while let Some(arg) = args.next() {
                if arg == "--out-dir" {
                    out_dir = PathBuf::from(parse_flag(&mut args, "--out-dir")?);
                } else {
                    return Err(format!("unknown option {arg}"));
                }
            }
            for path in [&baseline, &current] {
                if !path.exists() {
                    return Err(format!("Not found: {}", path.display()));
                }
            }
            let comparison = agentrouter_evaluation::compare_results(
                &agentrouter_evaluation::load_result(&baseline).map_err(|e| e.to_string())?,
                &agentrouter_evaluation::load_result(&current).map_err(|e| e.to_string())?,
            );
            for file in agentrouter_evaluation::write_comparison(&comparison, &out_dir)
                .map_err(|e| e.to_string())?
            {
                println!("Wrote {}", out_dir.join(file).display());
            }
            println!("\nGrade delta: {}", comparison["grade_delta"]);
            println!(
                "Critical regression: {}",
                if comparison["has_critical_regression"].as_bool() == Some(true) {
                    "YES"
                } else {
                    "NO"
                }
            );
            Ok(
                if comparison["has_critical_regression"].as_bool() == Some(true) {
                    1
                } else {
                    0
                },
            )
        }
        "status" | "prepare" => {
            let root = project_root();
            let mut names = Vec::new();
            let mut all = false;
            let mut dataset = None;
            let mut limit = None;
            while let Some(arg) = args.next() {
                match arg.as_str() {
                    "--all" => all = true,
                    "--dataset" => dataset = Some(parse_flag(&mut args, "--dataset")?),
                    "--limit" => limit = Some(parse_i64(&mut args, "--limit")?),
                    _ => return Err(format!("unknown option {arg}")),
                }
            }
            if command == "prepare" && dataset.is_none() && !all {
                return Err("Specify --dataset <name> or --all.".to_owned());
            }
            if command == "status" || all {
                names.extend(
                    agentrouter_evaluation::DATASET_NAMES
                        .iter()
                        .map(|name| (*name).to_owned()),
                );
            } else if let Some(dataset) = dataset {
                names.push(dataset);
            }
            if command == "prepare" {
                for name in &names {
                    let collection = agentrouter_evaluation::registry_api::collect(
                        &[name],
                        &root,
                        limit,
                        0,
                        "real",
                        None,
                    )?;
                    let info = &collection.datasets[name];
                    println!(
                        "{name:<16} SKIPPED_EXTERNAL  {}",
                        info["blocker"]
                            .as_str()
                            .unwrap_or("real preparation is unavailable")
                    );
                }
                return Ok(1);
            }
            println!(
                "{:16} {:9} {:6} blocker/notes",
                "dataset", "fixture", "real"
            );
            for name in names {
                let collected = agentrouter_evaluation::registry_api::collect(
                    &[name.as_str()],
                    &root,
                    None,
                    0,
                    "fixture",
                    None,
                )?;
                let fixture = !collected.cases.is_empty();
                let spec = agentrouter_evaluation::registry_api::dataset_spec(&name)?;
                let (_, reason) =
                    agentrouter_evaluation::adapter_real_availability(&name, spec.hf_repo);
                println!(
                    "{name:<16} {:9} {:6} {reason}",
                    if fixture { "yes" } else { "no" },
                    "no"
                );
            }
            Ok(0)
        }
        "context-band-generalization" => {
            let json_output = args.any(|arg| arg == "--json");
            let result = agentrouter_evaluation::context_bands::evaluate_generalization()?;
            if json_output {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&result).map_err(|e| e.to_string())?
                );
            } else {
                println!("Holdout SHA-256: {}", result["holdout_sha256"]);
                println!(
                    "Current accuracy: {}  95% CI {}",
                    result["current_holdout"]["accuracy"],
                    result["current_holdout"]["accuracy_ci95"]
                );
                println!(
                    "Current macro-F1: {}",
                    result["current_holdout"]["macro_f1"]
                );
                println!(
                    "Per-band recall: {}",
                    result["current_holdout"]["per_band_recall"]
                );
                println!(
                    "Pre-TASK-004 accuracy: {}",
                    result["pre_task004_holdout"]["accuracy"]
                );
                println!("Accuracy delta: {}", result["delta"]["accuracy"]);
            }
            Ok(0)
        }
        "--help" | "-h" | "help" => {
            println!("{}", usage());
            Ok(0)
        }
        _ => Err(format!("unknown command '{command}'\n{}", usage())),
    }
}

fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("{error}");
            let usage_error = error == usage()
                || error.starts_with("unknown command")
                || error.starts_with("unknown option")
                || error.starts_with("--")
                || error.starts_with("Invalid --source");
            std::process::exit(if usage_error { 2 } else { 3 });
        }
    }
}
