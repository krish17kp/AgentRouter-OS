//! Compatibility probe for `agentrouter providers status`.
//!
//! Usage: providers_status_cli <home>

use std::path::PathBuf;

use chrono::Local;

fn run() -> Result<(), (i32, String)> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or((2, "usage: providers_status_cli <home>".to_string()))?,
    );
    if args.next().is_some() {
        return Err((2, "usage: providers_status_cli <home>".to_string()));
    }
    let reg_dir = home.join("registry");
    if !reg_dir.is_dir() {
        return Err((
            3,
            format!(
                "Registry directory not found: {}\nNext: run agentrouter init first.",
                reg_dir.display()
            ),
        ));
    }
    let statuses = agentrouter_registry::catalog_ops::list_generated(
        &reg_dir,
        Local::now().date_naive(),
    )
    .map_err(|error| {
        (
            3,
            format!(
                "Cannot read catalog status: {error}\nNext: agentrouter providers doctor  (isolates which catalog is bad)"
            ),
        )
    })?;
    if statuses.is_empty() {
        println!("No refreshed catalogs. Manual models.yaml is authoritative.");
        println!("Next: agentrouter providers refresh openrouter");
        return Ok(());
    }
    for status in &statuses {
        println!("{}", status.summary());
    }
    if statuses.iter().any(|status| status.stale) {
        println!("\nSome catalogs are stale; re-run 'agentrouter providers refresh <provider>'.");
    }
    Ok(())
}

fn main() {
    if let Err((code, message)) = run() {
        eprintln!("{message}");
        std::process::exit(code);
    }
}
