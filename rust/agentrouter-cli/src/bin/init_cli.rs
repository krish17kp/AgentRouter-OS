//! Compatibility probe for `agentrouter init`.
//!
//! Usage: init_cli <home> [--force]

use std::path::PathBuf;

fn main() {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(args.next().expect("usage: init_cli <home> [--force]"));
    let force = match args.next().as_deref() {
        None => false,
        Some("--force") if args.next().is_none() => true,
        _ => {
            eprintln!("usage: init_cli <home> [--force]");
            std::process::exit(2);
        }
    };
    match agentrouter_cli::init_home_with_force(&home, force) {
        Ok(lines) => {
            for line in lines {
                println!("{line}");
            }
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(3);
        }
    }
}
