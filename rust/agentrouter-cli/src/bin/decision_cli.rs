//! Compatibility probe for the Rust `explain --json` and
//! `prompt generate --from` paths against a real Python-created decision log.
//!
//! Usage: decision_cli <home> <explain|prompt> <decision_id> [tool]

use std::path::PathBuf;

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or("usage: decision_cli <home> <op> <id> [tool]")?,
    );
    let op = args.next().ok_or("operation is required")?;
    let id = args.next().ok_or("decision id is required")?;
    let conn = agentrouter_storage::connect(&home).map_err(|e| e.to_string())?;
    let payload = agentrouter_storage::load_decision(&conn, &id)
        .map_err(|e| e.to_string())?
        .ok_or_else(|| format!("No decision found with id '{id}'."))?;
    match op.as_str() {
        "explain" => println!(
            "{}",
            serde_json::to_string(&payload).map_err(|e| e.to_string())?
        ),
        "prompt" => {
            let prompt = agentrouter_cli::prompt_from_decision(&payload, args.next().as_deref())?;
            print!("{prompt}");
        }
        _ => return Err(format!("unknown operation '{op}'")),
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
