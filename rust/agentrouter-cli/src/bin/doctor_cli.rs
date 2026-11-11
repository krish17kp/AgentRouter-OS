//! Rust counterpart for the structured `agentrouter doctor` report.
//!
//! Usage: doctor_cli <home> [--json] [--verify-live]

use std::path::PathBuf;

use serde_json::json;

fn run() -> Result<i32, String> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or_else(|| "usage: doctor_cli <home> [--json] [--verify-live]".to_string())?,
    );
    let mut as_json = false;
    let mut verify_live = false;
    for arg in args {
        match arg.as_str() {
            "--json" => as_json = true,
            "--verify-live" => verify_live = true,
            _ => return Err(format!("unknown argument: {arg}")),
        }
    }

    let mut checks = agentrouter_cli::diagnostics::run_all(&home);
    if verify_live {
        checks.extend(agentrouter_cli::diagnostics::run_usage_checks());
    }
    let status = agentrouter_cli::diagnostics::worst(&checks);
    if as_json {
        println!(
            "{}",
            json!({"status": status, "home": home, "checks": checks})
        );
    } else {
        for check in &checks {
            println!(
                "[{:4}] {:22} {}",
                check.status.to_uppercase(),
                check.id,
                check.summary
            );
            if let Some(remedy) = &check.remedy {
                println!("      -> {remedy}");
            }
        }
        let failures = checks
            .iter()
            .filter(|check| check.status == agentrouter_cli::diagnostics::FAIL)
            .count();
        let warnings = checks
            .iter()
            .filter(|check| check.status == agentrouter_cli::diagnostics::WARN)
            .count();
        if failures > 0 {
            println!("\n{failures} problem(s) to fix.");
        } else if warnings > 0 {
            println!("\nEverything works. {warnings} note(s) above worth knowing about.");
        } else {
            println!("\nAll clear.");
        }
    }
    Ok(if status == agentrouter_cli::diagnostics::FAIL {
        1
    } else {
        0
    })
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
